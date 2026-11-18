from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from prototype.household_maintenance.store import MaintenanceStore


class MaintenanceStoreTest(unittest.TestCase):
    def test_demo_task_is_overdue_and_completion_recalculates_next_due(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MaintenanceStore.open(Path(directory) / "maintenance.json")
            task = store.seed_demo(now=datetime(2026, 11, 18, 12, tzinfo=UTC))

            self.assertEqual(task["title"], "Contrôler les détecteurs de fumée")
            self.assertEqual(task["status"], "overdue")
            self.assertEqual(task["next_due_at"], "2026-11-17T09:00:00+00:00")

            completed = store.complete(task["id"], now=datetime(2026, 11, 18, 12, tzinfo=UTC))

            self.assertEqual(completed["status"], "scheduled")
            self.assertEqual(completed["last_completed_at"], "2026-11-18T12:00:00+00:00")
            self.assertEqual(completed["next_due_at"], "2027-05-17T12:00:00+00:00")

    def test_list_filters_and_sorts_by_priority_then_due_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MaintenanceStore.open(Path(directory) / "maintenance.json")
            store.create(
                title="Basse priorité",
                due_at="2026-11-17T10:00:00+00:00",
                criticality="low",
                recurrence_days=30,
                now=datetime(2026, 11, 18, tzinfo=UTC),
            )
            urgent = store.create(
                title="Urgent",
                due_at="2026-11-19T10:00:00+00:00",
                criticality="critical",
                recurrence_days=30,
                now=datetime(2026, 11, 18, tzinfo=UTC),
            )

            tasks = store.list_tasks(
                status="all", sort="priority", now=datetime(2026, 11, 18, tzinfo=UTC)
            )

            self.assertEqual([task["title"] for task in tasks], ["Urgent", "Basse priorité"])
            self.assertEqual(tasks[0]["id"], urgent["id"])

    def test_invalid_update_does_not_persist_a_partial_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "maintenance.json"
            store = MaintenanceStore.open(path)
            task = store.create(
                title="Nettoyer la VMC",
                due_at="2026-11-20T09:00:00+00:00",
                recurrence_days=90,
                now=datetime(2026, 11, 18, tzinfo=UTC),
            )

            with self.assertRaises(ValueError):
                store.update(task["id"], {"advance_notice_days": "bad"})

            self.assertEqual(MaintenanceStore.open(path).get(task["id"])["advance_notice_days"], 7)

    def test_persistence_round_trip_is_versioned_and_retains_completion_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "maintenance.json"
            store = MaintenanceStore.open(path)
            task = store.create(
                title="Nettoyer la VMC",
                due_at="2026-11-20T09:00:00+00:00",
                criticality="normal",
                recurrence_days=90,
                now=datetime(2026, 11, 18, tzinfo=UTC),
            )
            store.complete(task["id"], now=datetime(2026, 11, 18, 10, tzinfo=UTC))

            reloaded = MaintenanceStore.open(path)

            self.assertEqual(reloaded.snapshot()["version"], 1)
            self.assertEqual(len(reloaded.snapshot()["completion_events"]), 1)
            self.assertEqual(
                reloaded.get(task["id"])["last_completed_at"], "2026-11-18T10:00:00+00:00"
            )


if __name__ == "__main__":
    unittest.main()
