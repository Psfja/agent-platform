# 并发验收：pip install locust && locust -f locustfile.py --host http://localhost:8000
# Web UI: http://localhost:8089 ；无头：locust -f locustfile.py --headless -u 50 -r 5 -t 60s
from locust import HttpUser, between, task

EMAIL = "admin@company.com"
PASSWORD = "Admin@2026"


class PlatformUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        response = self.client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if response.ok:
            self.token = response.json()["accessToken"]
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            self.token = None

    @task(4)
    def project_list(self):
        self.client.get("/api/v1/projects")

    @task(3)
    def project_detail(self):
        self.client.get("/api/v1/projects/leave-hub")

    @task(2)
    def tasks_tree(self):
        self.client.get("/api/v1/projects/leave-hub/tasks")

    @task(2)
    def iterations(self):
        self.client.get("/api/v1/projects/leave-hub/iterations")

    @task(1)
    def agent_types(self):
        self.client.get("/api/v1/admin/agent-types")

    @task(1)
    def monitoring(self):
        self.client.get("/api/v1/monitoring/summary")
