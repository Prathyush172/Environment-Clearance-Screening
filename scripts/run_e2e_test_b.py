import sys
import json
import time
import httpx

API_BASE = "http://127.0.0.1:8000"

payload = {
    "client_id": "client_test_b",
    "project_name": "Fintech Software Office",
    "description": "Development of enterprise SaaS platform with server room in tech park.",
    "sector_hint": "Software development",
    "location": {
        "state": "Karnataka"
    }
}

def main():
    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        headers = {"X-Correlation-ID": "corr-test-b-software"}
        print("[1] Submitting Test B screening request...")
        resp = client.post("/v1/screenings", json=payload, headers=headers)
        print(f"Status: {resp.status_code}")
        submit_data = resp.json()
        print(f"Submission response: {json.dumps(submit_data, indent=2)}")
        
        if resp.status_code not in (200, 202):
            print("Submission failed!")
            sys.exit(1)
            
        run_id = submit_data.get("run_id")
        print(f"\n[2] Polling run_id: {run_id}...")
        for poll_attempt in range(1, 30):
            time.sleep(1.5)
            status_resp = client.get(f"/v1/screenings/{run_id}")
            if status_resp.status_code == 200:
                result = status_resp.json()
                current_status = result.get("status")
                print(f"Poll #{poll_attempt}: status={current_status}")
                if current_status in ("COMPLETED", "FAILED", "ESCALATED"):
                    print("\n[3] Final Result Received:")
                    print(json.dumps(result, indent=2))
                    return
            else:
                print(f"Poll #{poll_attempt}: HTTP {status_resp.status_code} - {status_resp.text}")
                
        print("Polling timed out!")
        sys.exit(2)

if __name__ == "__main__":
    main()
