from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from prototype.household_maintenance.local_demo import LocalDemoServer


def request(base_url: str, path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if payload is None else {"Content-Type": "application/json"}
    with urlopen(Request(base_url + path, data=payload, headers=headers, method=method), timeout=3) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


class LocalDemoServerTest(unittest.TestCase):
    def test_panel_api_creates_filters_updates_and_completes_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with LocalDemoServer(Path(directory) / "maintenance.json") as server:
                status, created = request(
                    server.url,
                    "/api/household_maintenance/tasks",
                    "POST",
                    {
                        "title": "Nettoyer le filtre VMC",
                        "due_at": "2026-11-18T09:00:00+00:00",
                        "criticality": "high",
                        "recurrence_days": 90,
                    },
                )
                self.assertEqual(status, 201)
                self.assertEqual(created["task"]["status"], "overdue")

                _, listed = request(server.url, "/api/household_maintenance/tasks?status=overdue&sort=priority")
                self.assertEqual(
                    [task["title"] for task in listed["tasks"]],
                    ["Contrôler les détecteurs de fumée", "Nettoyer le filtre VMC"],
                )

                _, updated = request(
                    server.url,
                    f'/api/household_maintenance/tasks/{created["task"]["id"]}',
                    "PATCH",
                    {"location_label": "Buanderie"},
                )
                self.assertEqual(updated["task"]["location_label"], "Buanderie")

                _, completed = request(
                    server.url,
                    f'/api/household_maintenance/tasks/{created["task"]["id"]}/complete',
                    "POST",
                )
                self.assertEqual(completed["task"]["status"], "scheduled")
                self.assertEqual(completed["summary"]["overdue"], 1)

    def test_static_card_and_panel_are_served_by_the_local_demo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with LocalDemoServer(Path(directory) / "maintenance.json") as server:
                _, panel = request(server.url, "/health")
                self.assertEqual(panel["status"], "ok")
                with urlopen(server.url + "/panel.html", timeout=3) as response:
                    panel_html = response.read().decode("utf-8")
                with urlopen(server.url + "/household-maintenance-card.js", timeout=3) as response:
                    card_js = response.read().decode("utf-8")
                with urlopen(server.url + "/card-demo.html", timeout=3) as response:
                    card_demo = response.read().decode("utf-8")
                self.assertIn("household-maintenance-panel", panel_html)
                self.assertIn("panel_url", card_js)
                self.assertIn("household-maintenance-card", card_demo)


if __name__ == "__main__":
    unittest.main()
