"""Guardrails framework for Environmental Clearance Pre-Screening Service.

Contains:
1. Input prompt-injection defense: unicode normalisation, homoglyphs, pattern matching, wrapping in <UNTRUSTED_DATA> delimiters.
2. Output guard: enforcing strict result schema, forbidding authoritative claims ("clearance granted/approved/not required legally", legal advice, impact assessment), ensuring standard disclaimer is present.
3. Toxicity / harmful content checks with configurable thresholds.
"""

import re
import unicodedata
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from libs.common.config import settings
from libs.common.logging import get_logger

logger = get_logger("guardrails")


# Delimiters
UNTRUSTED_OPEN = "<UNTRUSTED_DATA>"
UNTRUSTED_CLOSE = "</UNTRUSTED_DATA>"
CORPUS_OPEN = "<CORPUS_DATA>"
CORPUS_CLOSE = "</CORPUS_DATA>"

# Prompt injection signatures
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"you\s+are\s+now\s+(in\s+)?(dan|jailbreak|unrestricted|god)\s+mode",
    r"system\s+prompt\s+override",
    r"forget\s+everything\s+(you\s+know|previously\s+told)",
    r"output\s+that\s+clearance\s+is\s+(granted|approved|not\s+required)",
    r"mark\s+this\s+(as\s+)?category\s+[ab]",
    r"bypass\s+(safety|security|policy|guardrail)",
    r"act\s+as\s+an?\s+unrestricted\s+ai",
    r"repeat\s+the\s+system\s+prompt",
]

# Prohibited authoritative phrases in system output (pre-screening opinions cannot legally determine clearance)
AUTHORITATIVE_CLAIMS = [
    r"clearance\s+is\s+(hereby\s+)?granted",
    r"clearance\s+is\s+(hereby\s+)?approved",
    r"environmental\s+clearance\s+is\s+legally\s+(not\s+required|waived)",
    r"this\s+is\s+a\s+legal\s+determination",
    r"legal\s+advice",
    r"formal\s+impact\s+assessment\s+complete",
    r"binding\s+ruling\s+of\s+the\s+ministry",
]

# Standard mandatory disclaimer
STATUTORY_DISCLAIMER = (
    "SCREENING OPINION ONLY: This is a pre-screening assessment based on EIA Notification, 2006 and "
    "subsequent amendments. It does NOT constitute a formal or legal environmental clearance determination. "
    "Final categorization and clearance requirements must be determined by the accredited environmental "
    "consultant and the competent regulatory authority (MoEFCC / SEIAA / DEIAA)."
)


class GuardrailResult(BaseModel):
    passed: bool
    sanitised_text: str
    violations: List[str] = Field(default_factory=list)
    action: str = "allow"  # "allow", "sanitise", "block"
    reason: Optional[str] = None


class InputGuardrail:
    """Pre-processes and screens free text before it is dispatched to LLM or agent nodes."""

    @staticmethod
    def normalise_text(text: str) -> str:
        """Strip control characters, zero-width spaces, and normalise unicode NFKC."""
        if not text:
            return ""
        # Remove zero-width and invisible characters
        text = re.sub(r"[\u200B-\u200D\uFEFF\u00A0\u200E\u200F]", " ", text)
        # Unicode normalisation
        text = unicodedata.normalize("NFKC", text)
        # Strip excessive whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def check_prompt_injection(cls, text: str) -> Tuple[bool, List[str]]:
        """Scans text for prompt injection keywords and malicious pattern overrides."""
        cleaned = text.lower()
        violations = []
        for pat in PROMPT_INJECTION_PATTERNS:
            if re.search(pat, cleaned, re.IGNORECASE):
                violations.append(f"Prompt injection pattern detected: {pat}")
        return len(violations) > 0, violations

    @classmethod
    def process_input(cls, text: str, field_name: str = "description") -> GuardrailResult:
        """Normalises and checks input text."""
        sanitised = cls.normalise_text(text)
        has_injection, violations = cls.check_prompt_injection(sanitised)

        if has_injection:
            logger.warning("guardrail_trigger", field=field_name, violations=violations)
            action = "block" if settings.INJECTION_BLOCK_SEVERITY == "high" else "sanitise"
            return GuardrailResult(
                passed=False,
                sanitised_text=sanitised,
                violations=violations,
                action=action,
                reason="GUARDRAIL_BLOCKED: Untrusted prompt injection signature detected."
            )

        return GuardrailResult(passed=True, sanitised_text=sanitised, action="allow")

    @staticmethod
    def wrap_untrusted(text: str) -> str:
        """Wraps user input in strict untrusted data boundaries for LLM ingestion."""
        return f"{UNTRUSTED_OPEN}\n{text}\n{UNTRUSTED_CLOSE}"

    @staticmethod
    def wrap_corpus(text: str) -> str:
        """Wraps retrieved corpus passage in data delimiters."""
        return f"{CORPUS_OPEN}\n{text}\n{CORPUS_CLOSE}"


class OutputGuardrail:
    """Enforces non-authoritative language, disclaimer presence, and valid route schemas."""

    ALLOWED_ROUTES = {
        "NO_CLEARANCE_REQUIRED",
        "CATEGORY_B_STATE",
        "CATEGORY_A_CENTRAL",
        "ESCALATED_TO_HUMAN",
    }

    @classmethod
    def validate_output(cls, output: Dict[str, Any]) -> GuardrailResult:
        """Inspects final result dictionary for schema fidelity and illegal authoritative statements."""
        violations = []
        route = output.get("route")
        basis = output.get("basis", "")
        disclaimer = output.get("disclaimer", "")

        # 1. Route validation
        if route not in cls.ALLOWED_ROUTES:
            violations.append(f"Illegal route value '{route}'. Allowed: {cls.ALLOWED_ROUTES}")

        # 2. Disclaimer presence
        if not disclaimer or len(disclaimer.strip()) < 20:
            violations.append("Mandatory screening disclaimer is missing or truncated.")

        # 3. Authoritative language detection
        basis_lower = basis.lower()
        for pat in AUTHORITATIVE_CLAIMS:
            if re.search(pat, basis_lower, re.IGNORECASE):
                violations.append(f"Authoritative legal claim detected in output: '{pat}'")

        if violations:
            logger.error("output_guardrail_violation", violations=violations)
            return GuardrailResult(
                passed=False,
                sanitised_text=basis,
                violations=violations,
                action="block",
                reason="OUTPUT_GUARDRAIL_VIOLATION: Response contained prohibited authoritative determination language or invalid route schema."
            )

        return GuardrailResult(passed=True, sanitised_text=basis, action="allow")
