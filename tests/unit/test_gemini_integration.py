"""Unit tests for Gemini LLM client, schemas, structured output parsing, and verifier integration."""

import pytest
import os
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from libs.common.llm.schemas import (
    IntakeExtractionSchema,
    GroundedRegulatoryExplanation,
    VerifierVerificationResult,
    EntailmentClaimCheck,
    ProximityEntity,
)
from libs.common.llm.gemini import GeminiClient
from services.verifier.main import app as verifier_app
from fastapi.testclient import TestClient


class TestGeminiSchemas:
    """Verifies strict Pydantic schemas for Gemini interactions."""

    def test_intake_extraction_schema_valid(self):
        data = {
            "project_summary": "Thermal power plant 450 MW capacity in Rajasthan.",
            "classified_sector": "Thermal Power Plants",
            "schedule_item_hint": "1(d)",
            "capacity_value": 450.0,
            "capacity_unit": "MW",
            "area_ha": 35.0,
            "proximities": [
                {
                    "feature_type": "national_park",
                    "distance_km": 7.0,
                    "raw_distance_text": "7 km from national park",
                    "is_ambiguous": False,
                }
            ],
            "is_out_of_corpus": False,
            "confidence": 0.95,
        }
        res = IntakeExtractionSchema.model_validate(data)
        assert res.classified_sector == "Thermal Power Plants"
        assert res.capacity_value == 450.0
        assert len(res.proximities) == 1
        assert res.proximities[0].distance_km == 7.0
        assert not res.is_out_of_corpus

    def test_grounded_regulatory_explanation_schema(self):
        data = {
            "regulatory_basis": "Item 1(d) Category B project within 10 km of National Park triggers General Condition.",
            "threshold_analysis": "Plant capacity is 450 MW (< 500 MW), placing it in Category B under Item 1(d).",
            "general_condition_analysis": "Distance is 7.0 km (< 10.0 km statutory threshold), upgrading appraisal to Central Category A.",
            "grounded_in_citations": True,
        }
        res = GroundedRegulatoryExplanation.model_validate(data)
        assert "Item 1(d)" in res.regulatory_basis
        assert res.grounded_in_citations is True

    def test_verifier_verification_result_schema(self):
        data = {
            "is_supported": True,
            "entailment_results": [
                {
                    "claim": "Capacity 450 MW is Category B",
                    "verdict": "SUPPORTED",
                    "supporting_chunk_id": "schedule_1d",
                    "explanation": "Schedule Item 1(d) specifies coal-based plants < 500 MW are Category B.",
                }
            ],
            "evidence_sufficiency": "HIGH",
            "hallucination_detected": False,
            "summary_verdict": "All draft determinations are fully backed by retrieved corpus passages.",
        }
        res = VerifierVerificationResult.model_validate(data)
        assert res.is_supported is True
        assert len(res.entailment_results) == 1
        assert res.entailment_results[0].verdict == "SUPPORTED"


class TestGeminiClient:
    """Verifies GeminiClient resilience, fallback, and token tracking."""

    def test_gemini_client_missing_key_raises(self, monkeypatch):
        from libs.common.config import settings
        monkeypatch.setattr(settings, "LLM_API_KEY", None)
        monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
        with patch.dict(os.environ, {"LLM_API_KEY": "", "GEMINI_API_KEY": ""}):
            client = GeminiClient(api_key=None)
            client.api_key = None
            with pytest.raises(ValueError, match="Gemini API key is not configured"):
                client._get_client()

    def test_gemini_token_cost_calculation(self):
        client = GeminiClient(api_key="mock-key-not-real")
        mock_resp = MagicMock()
        mock_resp.text = '{"message": "hello", "count": 1}'
        mock_resp.usage_metadata.prompt_token_count = 1000
        mock_resp.usage_metadata.candidates_token_count = 500
        mock_resp.usage_metadata.thoughts_token_count = 100
        mock_resp.usage_metadata.total_token_count = 1600

        from pydantic import BaseModel
        class Simple(BaseModel):
            message: str
            count: int

        mock_genai_client = MagicMock()
        mock_genai_client.models.generate_content.return_value = mock_resp
        client._sdk_client = mock_genai_client

        parsed, meta = client.generate_structured(
            prompt="test",
            response_schema=Simple,
        )
        assert parsed.message == "hello"
        assert meta["prompt_tokens"] == 1000
        assert meta["completion_tokens"] == 500
        assert meta["total_tokens"] == 1600
        assert meta["cost_usd"] > 0


@pytest.mark.asyncio
class TestVerifierBehavior:
    """Verifies Independent Verifier behavior under missing evidence and offline stub modes."""

    async def test_verifier_fails_on_empty_citations(self):
        from services.verifier.main import verify_draft, VerificationRequest
        req = VerificationRequest(
            run_id="test-run-1",
            draft={"schedule_entry": {"item_no": "1(a)"}, "citations": []},
            retrieved_passages=[{"chunk_id": "c1", "text": "passage"}]
        )
        data = await verify_draft(req)
        assert data["passed"] is False
        assert "citations_present" in data["failed_checks"]

    async def test_verifier_fails_on_empty_passages_when_gemini_configured(self, monkeypatch):
        from libs.common.config import settings
        from services.verifier.main import verify_draft, VerificationRequest
        monkeypatch.setattr(settings, "VERIFIER_LLM_PROVIDER", "gemini")
        req = VerificationRequest(
            run_id="test-run-2",
            draft={
                "schedule_entry": {"item_no": "1(d)"},
                "citations": [{"citation_id": "cite1", "chunk_id": "c1"}],
            },
            retrieved_passages=[]
        )
        data = await verify_draft(req)
        assert data["passed"] is False
        assert data["entailment_results"][0]["verdict"] == "UNSUPPORTED"

    async def test_verifier_stub_passes_valid_draft(self, monkeypatch):
        from libs.common.config import settings
        from services.verifier.main import verify_draft, VerificationRequest
        monkeypatch.setattr(settings, "VERIFIER_LLM_PROVIDER", "stub")
        monkeypatch.setattr(settings, "LLM_PROVIDER", "stub")
        req = VerificationRequest(
            run_id="test-run-3",
            draft={
                "schedule_entry": {"item_no": "1(a)"},
                "citations": [{"citation_id": "cite1", "chunk_id": "c1"}],
                "proposed_route": "CATEGORY_B_STATE",
                "basis": "Standard Schedule Item 1(a) Category B determination."
            },
            retrieved_passages=[{"chunk_id": "c1", "text": "Mining lease < 50 ha is Category B"}]
        )
        data = await verify_draft(req)
        assert data["passed"] is True
        assert data["status"] == "PASSED"
        assert data["entailment_results"][0]["verdict"] == "SUPPORTED"

    async def test_verifier_returns_explicit_error_status_on_429(self, monkeypatch):
        """Regression test for live run 47a68d46-9944-40ea-bdd7-e8e2e9d1bb52:
        When Gemini encounters 429 quota exhaustion, verifier must fail-closed with status ERROR."""
        from libs.common.config import settings
        from services.verifier.main import verify_draft, VerificationRequest
        monkeypatch.setattr(settings, "VERIFIER_LLM_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
        monkeypatch.setattr(settings, "LLM_API_KEY", "fake-key")

        with patch("services.verifier.main.GeminiClient.generate_structured") as mock_gen:
            mock_gen.side_effect = Exception("429 RESOURCE_EXHAUSTED: quota limit exceeded")

            req = VerificationRequest(
                run_id="47a68d46-9944-40ea-bdd7-e8e2e9d1bb52",
                draft={
                    "proposed_route": "CATEGORY_A_CENTRAL",
                    "schedule_entry": {"item_no": "1(d)"},
                    "citations": [{"citation_id": "c1", "chunk_id": "chunk1"}],
                    "basis": "Thermal power plant within 10 km.",
                },
                retrieved_passages=[{"chunk_id": "chunk1", "text": "passage"}]
            )
            data = await verify_draft(req)
            assert data["passed"] is False
            assert data["status"] == "ERROR"
            assert "independent_llm_entailment" in data["failed_checks"]
            assert data["entailment_results"][0]["verdict"] == "UNSUPPORTED"
            assert "429" in data["entailment_results"][0]["explanation"]

    async def test_graph_finalize_preserves_verifier_status(self):
        """Ensure node_finalize populates explicit status and does not mask failures."""
        from services.worker.graph_agent import ScreeningAgentGraph
        from services.worker.graph_state import AgentState

        graph = ScreeningAgentGraph()
        state = AgentState(
            run_id="test-finalize-status",
            correlation_id="corr-1",
            request_data={"description": "Test"},
            start_time=100.0,
        )
        state.verification_report = {
            "passed": False,
            "checks": [{"check_name": "independent_llm_entailment", "passed": False, "detail": "429 RESOURCE_EXHAUSTED"}],
            "failed_checks": ["independent_llm_entailment"],
        }
        finalized = await graph.node_finalize(state)
        v = finalized.final_result["verification"]
        assert v["passed"] is False
        assert v["status"] == "ERROR"
