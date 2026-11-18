from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

SCHEMA_VERSION = 1
CRITICALITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Les dates doivent inclure un fuseau horaire")
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _status(task: dict, now: datetime) -> str:
    if task.get("archived"):
        return "archived"
    due_at = _parse_datetime(task["next_due_at"])
    if due_at < now:
        return "overdue"
    if due_at.date() == now.date():
        return "due_today"
    if due_at <= now + timedelta(days=task["advance_notice_days"]):
        return "upcoming"
    return "scheduled"


class MaintenanceStore:
    """Small versioned JSON store, deliberately independent of Home Assistant runtime."""

    def __init__(self, path: Path, data: dict) -> None:
        self.path = path
        self.data = data

    @classmethod
    def open(cls, path: Path) -> "MaintenanceStore":
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") != SCHEMA_VERSION:
                raise ValueError("Version de stockage non prise en charge")
        else:
            data = {"version": SCHEMA_VERSION, "tasks": [], "completion_events": []}
        return cls(path, data)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def snapshot(self) -> dict:
        return json.loads(json.dumps(self.data))

    def _present(self, task: dict, now: datetime) -> dict:
        output = dict(task)
        output["status"] = _status(task, now)
        return output

    def get(self, task_id: str, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        for task in self.data["tasks"]:
            if task["id"] == task_id:
                return self._present(task, now)
        raise KeyError(task_id)

    def create(
        self,
        *,
        title: str,
        due_at: str,
        criticality: str = "normal",
        recurrence_days: int = 30,
        category: str = "other",
        location_label: str | None = None,
        advance_notice_days: int = 7,
        now: datetime | None = None,
    ) -> dict:
        now = now or datetime.now(UTC)
        if not title.strip():
            raise ValueError("Le titre est obligatoire")
        if criticality not in CRITICALITY_ORDER:
            raise ValueError("Criticité invalide")
        if recurrence_days < 1 or advance_notice_days < 0:
            raise ValueError("Cadence ou préavis invalide")
        due = _parse_datetime(due_at)
        task = {
            "id": str(uuid4()),
            "title": title.strip(),
            "description": None,
            "category": category,
            "location_label": location_label,
            "recurrence_days": recurrence_days,
            "last_completed_at": None,
            "next_due_at": _iso(due),
            "advance_notice_days": advance_notice_days,
            "criticality": criticality,
            "tags": [],
            "archived": False,
            "created_at": _iso(now),
            "updated_at": _iso(now),
        }
        self.data["tasks"].append(task)
        self._save()
        return self._present(task, now)

    def update(self, task_id: str, changes: dict, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        allowed = {"title", "next_due_at", "criticality", "category", "location_label", "recurrence_days", "advance_notice_days", "archived"}
        if not isinstance(changes, dict) or set(changes) - allowed:
            raise ValueError("Champ de modification interdit")
        task = next((item for item in self.data["tasks"] if item["id"] == task_id), None)
        if task is None:
            raise KeyError(task_id)
        updates = dict(changes)
        if "title" in updates:
            if not isinstance(updates["title"], str) or not updates["title"].strip():
                raise ValueError("Le titre est obligatoire")
            updates["title"] = updates["title"].strip()
        if "criticality" in updates and updates["criticality"] not in CRITICALITY_ORDER:
            raise ValueError("Criticité invalide")
        if "next_due_at" in updates:
            updates["next_due_at"] = _iso(_parse_datetime(updates["next_due_at"]))
        for field in ("recurrence_days", "advance_notice_days"):
            if field in updates and (type(updates[field]) is not int or updates[field] < 0):
                raise ValueError("Cadence ou préavis invalide")
        if "recurrence_days" in updates and updates["recurrence_days"] < 1:
            raise ValueError("Cadence ou préavis invalide")
        if "archived" in updates and type(updates["archived"]) is not bool:
            raise ValueError("Archivage invalide")
        if "category" in updates and not isinstance(updates["category"], str):
            raise ValueError("Catégorie invalide")
        if "location_label" in updates and updates["location_label"] is not None and not isinstance(updates["location_label"], str):
            raise ValueError("Localisation invalide")
        candidate = {**task, **updates, "updated_at": _iso(now)}
        self._present(candidate, now)
        task.update(candidate)
        self._save()
        return self._present(task, now)

    def complete(self, task_id: str, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        task = next((item for item in self.data["tasks"] if item["id"] == task_id), None)
        if task is None:
            raise KeyError(task_id)
        previous_due_at = task["next_due_at"]
        task["last_completed_at"] = _iso(now)
        task["next_due_at"] = _iso(now + timedelta(days=task["recurrence_days"]))
        task["updated_at"] = _iso(now)
        self.data["completion_events"].append({
            "id": str(uuid4()),
            "task_id": task_id,
            "completed_at": _iso(now),
            "source": "panel",
            "previous_due_at": previous_due_at,
        })
        self._save()
        return self._present(task, now)

    def list_tasks(self, *, status: str = "all", sort: str = "priority", now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(UTC)
        tasks = [self._present(task, now) for task in self.data["tasks"]]
        if status != "all":
            tasks = [task for task in tasks if task["status"] == status]
        if sort == "priority":
            tasks.sort(key=lambda task: (CRITICALITY_ORDER[task["criticality"]], task["next_due_at"], task["title"].casefold()))
        elif sort == "due":
            tasks.sort(key=lambda task: (task["next_due_at"], CRITICALITY_ORDER[task["criticality"]], task["title"].casefold()))
        else:
            raise ValueError("Tri invalide")
        return tasks

    def seed_demo(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        existing = next((task for task in self.data["tasks"] if task["title"] == "Contrôler les détecteurs de fumée"), None)
        if existing:
            return self._present(existing, now)
        return self.create(
            title="Contrôler les détecteurs de fumée",
            due_at="2026-11-17T09:00:00+00:00",
            criticality="critical",
            recurrence_days=180,
            category="safety",
            location_label="Salon",
            advance_notice_days=14,
            now=now,
        )
