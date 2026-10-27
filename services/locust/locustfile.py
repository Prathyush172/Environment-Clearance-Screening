from locust import HttpUser, task, between
import uuid

class ScreeningUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def submit_screening(self):
        payload = {
            "client_id": "locust-client",
            "project_name": "Test Mining Project",
            "description": "Commercial iron ore open cast mining covering 45 hectares in Bellary district.",
            "location": {
                "state": "Karnataka",
                "district": "Bellary"
            }
        }
        headers = {"X-Correlation-ID": str(uuid.uuid4())}
        with self.client.post("/v1/screenings", json=payload, headers=headers, catch_response=True) as resp:
            if resp.status_code == 202:
                resp.success()
            else:
                resp.failure(f"Failed with {resp.status_code}")
