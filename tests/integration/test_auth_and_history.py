"""Integration tests for Login, Auth, Data Isolation, History, and Escalation."""

import pytest
import time
import uuid
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from services.api.main import app
from services.api.auth import hash_password, verify_password, create_access_token
from libs.common.db.session import get_db_session, init_db
from libs.common.db.models import User, UserSession, Run, RunStatus, ScreeningRoute
from libs.common.config import settings

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_users():
    """Ensure database tables and dedicated test accounts exist."""
    import asyncio

    async def _setup():
        await init_db()
        async with get_db_session() as session:
            # Create user A
            q_a = select(User).where(User.username == "test_user_a")
            res_a = await session.execute(q_a)
            if not res_a.scalar_one_or_none():
                user_a = User(
                    id="user-uuid-a-1111",
                    email="usera@eia.gov.in",
                    username="test_user_a",
                    hashed_password=hash_password("PassUserA123!"),
                    full_name="User Alpha",
                    role="user",
                    client_id="client_tenant_alpha",
                    is_active=True,
                )
                session.add(user_a)

            # Create user B
            q_b = select(User).where(User.username == "test_user_b")
            res_b = await session.execute(q_b)
            if not res_b.scalar_one_or_none():
                user_b = User(
                    id="user-uuid-b-2222",
                    email="userb@eia.gov.in",
                    username="test_user_b",
                    hashed_password=hash_password("PassUserB123!"),
                    full_name="User Beta",
                    role="user",
                    client_id="client_tenant_beta",
                    is_active=True,
                )
                session.add(user_b)

            # Create Admin
            q_adm = select(User).where(User.username == "test_admin")
            res_adm = await session.execute(q_adm)
            if not res_adm.scalar_one_or_none():
                admin = User(
                    id="user-uuid-admin-9999",
                    email="admin_test@eia.gov.in",
                    username="test_admin",
                    hashed_password=hash_password("AdminSecure999!"),
                    full_name="Security Admin",
                    role="admin",
                    client_id="client_admin_tenant",
                    is_active=True,
                )
                session.add(admin)

    asyncio.run(_setup())


# ==============================================================================
# 1. AUTHENTICATION TESTS
# ==============================================================================

def test_login_successful():
    """Valid credentials return JWT access token and user profile."""
    resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_a", "password": "PassUserA123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "test_user_a"
    assert data["user"]["client_id"] == "client_tenant_alpha"


def test_login_with_email_successful():
    """Valid email login works interchangeably with username."""
    resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "usera@eia.gov.in", "password": "PassUserA123!"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_invalid_password_fails():
    """Invalid password returns 401 Unauthorized."""
    resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_a", "password": "WrongPassword!"},
    )
    assert resp.status_code == 401
    assert "Invalid username/email or password" in resp.json()["detail"]


def test_login_nonexistent_user_fails():
    """Non-existent user returns 401 Unauthorized."""
    resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "nonexistent_user_xyz", "password": "AnyPassword!"},
    )
    assert resp.status_code == 401


def test_login_missing_required_fields():
    """Missing required fields return 422 Unprocessable Entity."""
    resp = client.post("/v1/auth/login", json={"username_or_email": "test_user_a"})
    assert resp.status_code == 422


def test_passwords_stored_as_bcrypt_hashes():
    """Passwords must be hashed with bcrypt; plaintext must never be stored."""
    import asyncio

    async def _check():
        async with get_db_session() as session:
            q = select(User).where(User.username == "test_user_a")
            res = await session.execute(q)
            user = res.scalar_one()
            # Must start with standard bcrypt prefix
            assert user.hashed_password.startswith("$2b$")
            assert user.hashed_password != "PassUserA123!"
            assert verify_password("PassUserA123!", user.hashed_password) is True
            assert verify_password("FakePass", user.hashed_password) is False

    asyncio.run(_check())


def test_logout_revokes_session():
    """Logging out revokes the active token so subsequent requests are rejected."""
    # 1. Login
    login_resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_a", "password": "PassUserA123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify token works
    me_resp = client.get("/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200

    # 3. Logout
    logout_resp = client.post("/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "logged_out"

    # 4. Attempt to reuse revoked token
    reuse_resp = client.get("/v1/auth/me", headers=headers)
    assert reuse_resp.status_code == 401
    assert "revoked" in reuse_resp.json()["detail"].lower()


def test_tampered_or_invalid_token_rejected():
    """Tampered token fails verification with 401."""
    resp = client.get("/v1/auth/me", headers={"Authorization": "Bearer invalid.token.value"})
    assert resp.status_code == 401


# ==============================================================================
# 2. AUTHORIZATION & DATA ISOLATION TESTS
# ==============================================================================

def test_unauthenticated_request_rejected():
    """Protected endpoints reject unauthenticated requests with 401."""
    resp = client.get("/v1/screenings")
    assert resp.status_code == 401


def test_authenticated_submission_binds_user_client_id():
    """Screening submission binds client_id to authenticated user, ignoring client spoofing."""
    # Login User A
    login_a = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_a", "password": "PassUserA123!"},
    )
    token_a = login_a.json()["access_token"]

    payload = {
        "client_id": "malicious_spoofed_client",  # Spoofing attempt
        "project_name": "Isolated Alpha Mining Project",
        "description": "Commercial mining proposal over 40 ha with strict environmental mitigations.",
        "sector_hint": "Mining of minerals",
        "location": {"state": "Karnataka"},
    }

    sub_resp = client.post(
        "/v1/screenings",
        json=payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert sub_resp.status_code == 202
    run_id = sub_resp.json()["run_id"]

    # Verify run record in DB has User A's client_id
    get_resp = client.get(
        f"/v1/screenings/{run_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["client_id"] == "client_tenant_alpha"  # Bound, not spoofed


def test_user_a_cannot_access_user_b_screening():
    """User B cannot access User A's screening record (403 Forbidden)."""
    # Login User A & submit
    login_a = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_a", "password": "PassUserA123!"},
    )
    token_a = login_a.json()["access_token"]

    sub_resp = client.post(
        "/v1/screenings",
        json={
            "client_id": "client_tenant_alpha",
            "project_name": "Confidential Alpha Mine",
            "description": "Sensitive industrial project located in Karnataka.",
            "location": {"state": "Karnataka"},
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    run_id_a = sub_resp.json()["run_id"]

    # Login User B
    login_b = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_b", "password": "PassUserB123!"},
    )
    token_b = login_b.json()["access_token"]

    # User B attempts to access User A's run
    cross_resp = client.get(
        f"/v1/screenings/{run_id_a}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_resp.status_code == 403
    assert "Forbidden" in cross_resp.json()["detail"]


def test_admin_can_access_any_user_screening():
    """Admin role has authorization to view any screening record."""
    # Login User A & submit
    login_a = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_a", "password": "PassUserA123!"},
    )
    token_a = login_a.json()["access_token"]

    sub_resp = client.post(
        "/v1/screenings",
        json={
            "client_id": "client_tenant_alpha",
            "project_name": "Audit Tracked Project",
            "description": "Mining proposal in Karnataka requiring regulatory oversight.",
            "location": {"state": "Karnataka"},
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    run_id = sub_resp.json()["run_id"]

    # Login Admin
    login_adm = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_admin", "password": "AdminSecure999!"},
    )
    token_adm = login_adm.json()["access_token"]

    # Admin reads User A's run
    adm_resp = client.get(
        f"/v1/screenings/{run_id}",
        headers={"Authorization": f"Bearer {token_adm}"},
    )
    assert adm_resp.status_code == 200
    assert adm_resp.json()["run_id"] == run_id


def test_regular_user_cannot_access_quarantine():
    """Regular user accessing quarantine endpoint is rejected with 403."""
    login_a = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_a", "password": "PassUserA123!"},
    )
    token_a = login_a.json()["access_token"]

    resp = client.get("/v1/quarantine", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 403


# ==============================================================================
# 3. SCREENING HISTORY TESTS
# ==============================================================================

def test_screening_history_scopes_records_to_authenticated_user():
    """History endpoint only returns records for the authenticated tenant."""
    # Login User A
    login_a = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_a", "password": "PassUserA123!"},
    )
    token_a = login_a.json()["access_token"]

    hist_a = client.get("/v1/screenings", headers={"Authorization": f"Bearer {token_a}"})
    assert hist_a.status_code == 200
    data_a = hist_a.json()
    assert "items" in data_a
    assert "total" in data_a

    # All items returned must belong to User A's client_id
    for item in data_a["items"]:
        assert item["client_id"] == "client_tenant_alpha"


def test_screening_history_includes_completed_and_escalated_runs():
    """History returns both COMPLETED and ESCALATED runs properly structured."""
    import asyncio

    run_id_comp = str(uuid.uuid4())
    run_id_esc = str(uuid.uuid4())

    async def _insert_runs():
        async with get_db_session() as session:
            # Completed run
            comp = Run(
                id=run_id_comp,
                run_id=run_id_comp,
                correlation_id="corr-comp",
                client_id="client_tenant_alpha",
                user_id="user-uuid-a-1111",
                project_name="Completed Solar Farm",
                description="Solar installation with environmental classification completed.",
                status=RunStatus.COMPLETED,
                route=ScreeningRoute.NO_CLEARANCE_REQUIRED,
            )
            # Escalated run
            esc = Run(
                id=run_id_esc,
                run_id=run_id_esc,
                correlation_id="corr-esc",
                client_id="client_tenant_alpha",
                user_id="user-uuid-a-1111",
                project_name="Escalated SaaS Tech Park",
                description="Software campus requiring human review.",
                status=RunStatus.ESCALATED,
                route=ScreeningRoute.ESCALATED_TO_HUMAN,
                result_json={
                    "route": "ESCALATED_TO_HUMAN",
                    "escalation": {
                        "reason_code": "OUT_OF_CORPUS_SECTOR",
                        "detail": "Software development sector not in EIA Schedule.",
                        "human_checklist": ["Confirm no heavy diesel generator sets installed."],
                    },
                    "disclaimer": "SCREENING OPINION ONLY",
                },
            )
            session.add(comp)
            session.add(esc)

    asyncio.run(_insert_runs())

    # Fetch history as User A
    login_a = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test_user_a", "password": "PassUserA123!"},
    )
    token_a = login_a.json()["access_token"]
    hist_resp = client.get("/v1/screenings", headers={"Authorization": f"Bearer {token_a}"})
    assert hist_resp.status_code == 200

    run_ids = [item["run_id"] for item in hist_resp.json()["items"]]
    assert run_id_comp in run_ids
    assert run_id_esc in run_ids

    # Fetch escalated run details
    esc_detail = client.get(f"/v1/screenings/{run_id_esc}", headers={"Authorization": f"Bearer {token_a}"})
    assert esc_detail.status_code == 200
    res = esc_detail.json()
    assert res["status"] == "ESCALATED"
    assert res["route"] == "ESCALATED_TO_HUMAN"
    assert res["result"]["escalation"]["reason_code"] == "OUT_OF_CORPUS_SECTOR"
