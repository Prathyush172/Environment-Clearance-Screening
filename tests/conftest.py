import sys
import os

# Prevent google-auth metadata check hang
os.environ["NO_GCE_CHECK"] = "true"

import pytest

# Ensure repository root is on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from libs.common.config import settings


@pytest.fixture(autouse=True)
def default_stub_settings(monkeypatch):
    """Ensure offline unit tests default to stub provider unless explicitly overridden."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "stub")
    monkeypatch.setattr(settings, "VERIFIER_LLM_PROVIDER", "stub")

