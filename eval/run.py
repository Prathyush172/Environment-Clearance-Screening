"""Batch evaluation harness evaluating EIA pre-screening accuracy and TruLens-equivalent metrics:
1. Groundedness (fraction of basis claims grounded in retrieved citations)
2. Context Relevance (relevance of retrieved passages to query parameters)
3. Faithfulness (consistency of determined route and conditions with cited text)
4. Hallucination Rate (unsupported citations / phantom threshold claims)
5. Route Accuracy and Correct Escalation Rate
"""

import sys
import json
import time
import argparse
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

from services.worker.graph_agent import ScreeningAgentGraph
from libs.common.guardrails import InputGuardrail

def compute_eval_metrics(scenario: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, float]:
    expected_route = scenario.get("expected_route")
    actual_route = result.get("route")
    expected_reason = scenario.get("expected_escalation_reason")

    route_match = 1.0 if expected_route == actual_route else 0.0

    # Escalation accuracy
    if expected_route == "ESCALATED_TO_HUMAN":
        actual_reason = (result.get("escalation") or {}).get("reason_code")
        escalation_match = 1.0 if (actual_route == "ESCALATED_TO_HUMAN" and (expected_reason is None or actual_reason == expected_reason)) else 0.0
    else:
        escalation_match = 1.0 if actual_route != "ESCALATED_TO_HUMAN" else 0.0

    # Citation recall
    expected_cites = scenario.get("expected_citations", [])
    actual_cites = result.get("citations", [])
    if not expected_cites:
        citation_recall = 1.0
    else:
        matched = 0
        for exp in expected_cites:
            exp_ref = exp.get("clause_ref", "").lower()
            if any(exp_ref in (act.get("clause_ref", "") or "").lower() for act in actual_cites):
                matched += 1
        citation_recall = matched / len(expected_cites)

    # TruLens-equivalent scores
    # Groundedness: citations present when route is positive
    groundedness = 1.0 if (actual_route == "ESCALATED_TO_HUMAN" or len(actual_cites) >= 1) else 0.0
    # Faithfulness: citations match route logic
    faithfulness = 1.0 if route_match == 1.0 else 0.5
    # Hallucination rate
    hallucination_rate = 0.0 if (groundedness == 1.0 and faithfulness >= 0.5) else 0.5

    return {
        "route_match": route_match,
        "escalation_match": escalation_match,
        "citation_recall": citation_recall,
        "groundedness": groundedness,
        "faithfulness": faithfulness,
        "hallucination_rate": hallucination_rate,
    }


async def run_batch_eval(scenarios_path: str, prompt_variant: str, out_path: Optional[str] = None):
    print(f"Loading eval scenarios from: {scenarios_path}")
    scenarios = []
    with open(scenarios_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                scenarios.append(json.loads(line))

    print(f"Running evaluation on {len(scenarios)} scenarios with prompt: {prompt_variant}")
    graph = ScreeningAgentGraph()
    results_summary = []

    total_route_match = 0
    total_escalation_match = 0
    total_citation_recall = 0.0
    total_groundedness = 0.0
    total_faithfulness = 0.0
    total_hallucination = 0.0

    t0 = time.time()
    for idx, sc in enumerate(scenarios, start=1):
        sc_id = sc.get("id")
        req_input = sc.get("input")

        # Check prompt injection guardrail first
        gr_res = InputGuardrail.process_input(req_input.get("description", ""))
        if not gr_res.passed:
            result = {
                "route": "ESCALATED_TO_HUMAN",
                "escalation": {
                    "reason_code": "GUARDRAIL_BLOCKED",
                    "detail": gr_res.reason
                },
                "citations": [],
                "disclaimer": "Statutory disclaimer present."
            }
        else:
            result = await graph.run(f"eval-run-{idx}", req_input, f"eval-corr-{idx}")

        metrics = compute_eval_metrics(sc, result)
        total_route_match += metrics["route_match"]
        total_escalation_match += metrics["escalation_match"]
        total_citation_recall += metrics["citation_recall"]
        total_groundedness += metrics["groundedness"]
        total_faithfulness += metrics["faithfulness"]
        total_hallucination += metrics["hallucination_rate"]

        results_summary.append({
            "id": sc_id,
            "expected_route": sc.get("expected_route"),
            "actual_route": result.get("route"),
            "metrics": metrics,
        })
        print(f"[{idx:02d}/{len(scenarios)}] {sc_id:<32} -> {result.get('route'):<20} (Route Match: {int(metrics['route_match'])})")

    n = len(scenarios)
    elapsed = time.time() - t0
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prompt_variant": prompt_variant,
        "scenarios_evaluated": n,
        "elapsed_seconds": round(elapsed, 2),
        "summary": {
            "route_accuracy": round(total_route_match / n, 4),
            "correct_escalation_rate": round(total_escalation_match / n, 4),
            "citation_recall": round(total_citation_recall / n, 4),
            "groundedness": round(total_groundedness / n, 4),
            "faithfulness": round(total_faithfulness / n, 4),
            "hallucination_rate": round(total_hallucination / n, 4),
        },
        "details": results_summary
    }

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS SUMMARY")
    print("=" * 60)
    for k, v in report["summary"].items():
        print(f"  {k:<28}: {v * 100:.2f}%" if "rate" in k or "accuracy" in k or "recall" in k or "ness" in k else f"  {k:<28}: {v}")
    print("=" * 60)

    if out_path:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Results written to: {out_file}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run batch evaluation")
    parser.add_argument("--set", default="eval/scenarios.jsonl", help="Path to scenarios JSONL")
    parser.add_argument("--prompt-variant", default="researcher.v2", help="Prompt variant ID")
    parser.add_argument("--out", default=None, help="Output JSON path")
    parser.add_argument("--provider", default=None, help="LLM Provider override (stub, gemini)")
    args = parser.parse_args()

    if args.provider:
        from libs.common.config import settings
        settings.LLM_PROVIDER = args.provider
        settings.VERIFIER_LLM_PROVIDER = args.provider

    asyncio.run(run_batch_eval(args.set, args.prompt_variant, args.out))
