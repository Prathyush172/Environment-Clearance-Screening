"""Complete End-to-End Demonstration Script for Login, Screening, Escalation, History, and Isolation."""

import sys
import json
import time
import httpx

API_BASE = "http://127.0.0.1:8000"


def main():
    print("=" * 70)
    print("EIA PRE-SCREENING SYSTEM: LIVE END-TO-END DEMONSTRATION")
    print("=" * 70)

    client = httpx.Client(base_url=API_BASE, timeout=60.0)

    # --------------------------------------------------------------------------
    # Step 1: Login using development account (officer)
    # --------------------------------------------------------------------------
    print("\n[Step 1] Logging in with development account 'officer'...")
    login_resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "officer", "password": "OfficerPass123!"},
    )
    print(f"Status Code: {login_resp.status_code}")
    login_data = login_resp.json()
    token = login_data["access_token"]
    user_info = login_data["user"]
    print(f"Authenticated as: {user_info['username']} ({user_info['email']})")
    print(f"Role: {user_info['role']} | Tenant Client ID: {user_info['client_id']}")
    print(f"JWT Access Token: {token[:20]}...{token[-15:]}")

    auth_headers = {"Authorization": f"Bearer {token}"}

    # --------------------------------------------------------------------------
    # Step 2: Submit Scenario A (Thermal Power Plant - Category A Central)
    # --------------------------------------------------------------------------
    print("\n[Step 2] Submitting Scenario A: Thermal Power Plant (7 km from National Park)...")
    payload_a = {
        "client_id": user_info["client_id"],
        "project_name": "Thermal Power Plant 7km from Park",
        "description": "Establishment of a 300 MW coal-based thermal power plant situated 7.0 km from the boundary of a notified National Park in Madhya Pradesh.",
        "sector_hint": "Thermal Power Plants",
        "capacity": {"value": 300.0, "unit": "MW"},
        "location": {"state": "Madhya Pradesh"},
        "proximity": [
            {
                "feature_type": "national_park",
                "distance_km": 7.0,
                "name": "Bandhavgarh National Park",
            }
        ],
    }

    sub_a_resp = client.post("/v1/screenings", json=payload_a, headers=auth_headers)
    assert sub_a_resp.status_code == 202, f"Expected 202, got {sub_a_resp.status_code}"
    run_id_a = sub_a_resp.json()["run_id"]
    print(f"Accepted with Run ID: {run_id_a} (Status: QUEUED)")

    # Poll until completed
    print(f"Polling Run A ({run_id_a})...")
    run_a_result = None
    for attempt in range(1, 25):
        time.sleep(1.5)
        r = client.get(f"/v1/screenings/{run_id_a}", headers=auth_headers)
        status_val = r.json().get("status")
        print(f"  Attempt {attempt}: status={status_val}")
        if status_val in ("COMPLETED", "ESCALATED", "FAILED"):
            run_a_result = r.json()
            break

    assert run_a_result is not None, "Scenario A timed out"
    print("\n--- Scenario A Final Result ---")
    print(f"Project: {run_a_result['project_name']}")
    print(f"Status: {run_a_result['status']}")
    print(f"Route: {run_a_result['route']}")
    print(f"Schedule Item: {run_a_result['result']['schedule_entry']['item_no']} ({run_a_result['result']['schedule_entry']['sector']})")
    print(f"Conditions Applied: {json.dumps(run_a_result['result']['conditions_applied'], indent=2)}")
    print(f"Citations Count: {len(run_a_result['result']['citations'])}")
    print(f"Verifier Status: Passed={run_a_result['result']['verification']['passed']}")
    print(f"Disclaimer Present: {'SCREENING OPINION ONLY' in run_a_result['result']['disclaimer']}")

    # --------------------------------------------------------------------------
    # Step 3: Submit Scenario B (Unsupported Sector - Fintech Software Office)
    # --------------------------------------------------------------------------
    print("\n[Step 3] Submitting Scenario B: Fintech Software Office (Unsupported Sector)...")
    payload_b = {
        "client_id": user_info["client_id"],
        "project_name": "Fintech Software Office",
        "description": "Development of enterprise SaaS platform with server room in tech park.",
        "sector_hint": "Software development",
        "location": {"state": "Karnataka"},
    }

    sub_b_resp = client.post("/v1/screenings", json=payload_b, headers=auth_headers)
    assert sub_b_resp.status_code == 202, f"Expected 202, got {sub_b_resp.status_code}"
    run_id_b = sub_b_resp.json()["run_id"]
    print(f"Accepted with Run ID: {run_id_b} (Status: QUEUED)")

    # Poll until completed
    print(f"Polling Run B ({run_id_b})...")
    run_b_result = None
    for attempt in range(1, 25):
        time.sleep(1.5)
        r = client.get(f"/v1/screenings/{run_id_b}", headers=auth_headers)
        status_val = r.json().get("status")
        print(f"  Attempt {attempt}: status={status_val}")
        if status_val in ("COMPLETED", "ESCALATED", "FAILED"):
            run_b_result = r.json()
            break

    assert run_b_result is not None, "Scenario B timed out"
    print("\n--- Scenario B Final Result (Escalation UI Payload) ---")
    print(f"Project: {run_b_result['project_name']}")
    print(f"Status: {run_b_result['status']}")
    print(f"Route: {run_b_result['route']}")
    print(f"Escalation Reason Code: {run_b_result['result']['escalation']['reason_code']}")
    print(f"Escalation Detail: {run_b_result['result']['escalation']['detail']}")
    print(f"Missing Information: {run_b_result['result']['escalation']['missing_info']}")
    print(f"Human Review Checklist: {run_b_result['result']['escalation']['human_checklist']}")
    print(f"Confidence: {run_b_result['result']['confidence']}")
    print(f"Disclaimer Present: {'SCREENING OPINION ONLY' in run_b_result['result']['disclaimer']}")

    # --------------------------------------------------------------------------
    # Step 4: Open Screening History
    # --------------------------------------------------------------------------
    print("\n[Step 4] Querying Screening History for 'officer'...")
    hist_resp = client.get("/v1/screenings", headers=auth_headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    print(f"Total Persisted Runs in History: {hist_data['total']}")
    for item in hist_data["items"][:5]:
        print(f"  - [{item['status']:<9}] {item['route']:<20} | {item['project_name']} (Run: {item['run_id'][:8]}...)")

    # Confirm both runs appear in history
    hist_run_ids = [it["run_id"] for it in hist_data["items"]]
    assert run_id_a in hist_run_ids, f"Run A ({run_id_a}) missing from history!"
    assert run_id_b in hist_run_ids, f"Run B ({run_id_b}) missing from history!"
    print("[OK] Verified: Both Scenario A and Scenario B appear in persisted history.")

    # --------------------------------------------------------------------------
    # Step 5: Data Isolation & Cross-User Security Check
    # --------------------------------------------------------------------------
    print("\n[Step 5] Testing Data Isolation with User 2 ('user2')...")
    login_u2 = client.post(
        "/v1/auth/login",
        json={"username_or_email": "user2", "password": "User2Pass123!"},
    )
    token_u2 = login_u2.json()["access_token"]
    u2_headers = {"Authorization": f"Bearer {token_u2}"}

    # User 2 tries to access Officer's Run A
    u2_access_a = client.get(f"/v1/screenings/{run_id_a}", headers=u2_headers)
    print(f"User 2 access to Officer's Run A: HTTP {u2_access_a.status_code} ({u2_access_a.json().get('detail')})")
    assert u2_access_a.status_code == 403, f"Expected 403 Forbidden, got {u2_access_a.status_code}"

    # User 2 queries their own history
    u2_hist = client.get("/v1/screenings", headers=u2_headers)
    u2_hist_ids = [it["run_id"] for it in u2_hist.json()["items"]]
    assert run_id_a not in u2_hist_ids, "Data leak: Officer's Run A appeared in User 2's history!"
    assert run_id_b not in u2_hist_ids, "Data leak: Officer's Run B appeared in User 2's history!"
    print(f"User 2 history count: {u2_hist.json()['total']} (Zero officer records leaked)")
    print("[OK] Verified: Data isolation prevents cross-tenant access.")

    # --------------------------------------------------------------------------
    # Step 6: Logout & Session Invalidation Check
    # --------------------------------------------------------------------------
    print("\n[Step 6] Logging out 'officer' and verifying token revocation...")
    logout_resp = client.post("/v1/auth/logout", headers=auth_headers)
    print(f"Logout HTTP Status: {logout_resp.status_code} ({logout_resp.json().get('message')})")

    # Try to access protected endpoint with revoked token
    after_logout_resp = client.get("/v1/screenings", headers=auth_headers)
    print(f"Access with revoked token: HTTP {after_logout_resp.status_code} ({after_logout_resp.json().get('detail')})")
    assert after_logout_resp.status_code == 401, f"Expected 401, got {after_logout_resp.status_code}"
    print("[OK] Verified: Revoked session tokens are blocked immediately.")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE: ALL 6 WORKFLOW VERIFICATIONS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
