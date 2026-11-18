"""Local asynchronous task persistence for Household Maintenance."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION

PRIORITIES = {"critical": 0, "high": 1, "normal": 2, "low": 3}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("due_at must include a timezone")
    return parsed.astimezone(UTC)


def _present(task: dict, now: datetime) -> dict:
    item = deepcopy(task)
    due_at = _date(item["due_at"])
    if due_at < now:
        item["status"] = "overdue"
    elif due_at.date() == now.date():
        item["status"] = "due_today"
    elif due_at <= now + timedelta(days=item["advance_notice_days"]):
        item["status"] = "upcoming"
    else:
        item["status"] = "scheduled"
    return item


class MaintenanceStore:
    """Single-writer Store-backed repository with an empty first-run state."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict = {"data_version": STORAGE_VERSION, "tasks": []}
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        raw = await self._store.async_load()
        if raw is None:
            return
        if not isinstance(raw, dict) or not isinstance(raw.get("tasks", []), list):
            raise ValueError("Stored maintenance data is invalid")
        # Version 0 was an unversioned list in early development; preserve it safely.
        self._data = {"data_version": STORAGE_VERSION, "tasks": raw.get("tasks", [])}

    async def _async_save(self) -> None:
        await self._store.async_save(self._data)

    async def async_list(self, status: str = "all", sort: str = "priority") -> list[dict]:
        now = _now()
        tasks = [_present(task, now) for task in self._data["tasks"]]
        if status != "all":
            tasks = [task for task in tasks if task["status"] == status]
        if sort == "priority":
            tasks.sort(key=lambda task: (PRIORITIES[task["priority"]], task["due_at"], task["title"].casefold()))
        elif sort == "due":
            tasks.sort(key=lambda task: (task["due_at"], PRIORITIES[task["priority"]], task["title"].casefold()))
        else:
            raise ValueError("sort must be priority or due")
        return tasks

    async def async_create(self, payload: dict) -> dict:
        title = payload.get("title", "")
        due_at = payload.get("due_at")
        priority = payload.get("priority", "normal")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title is required")
        if not isinstance(due_at, str):
            raise ValueError("due_at is required")
        due_at = _iso(_date(due_at))
        if priority not in PRIORITIES:
            raise ValueError("priority is invalid")
        notice = payload.get("advance_notice_days", 7)
        recurrence = payload.get("recurrence_days", 30)
        if type(notice) is not int or notice < 0 or type(recurrence) is not int or recurrence < 1:
            raise ValueError("recurrence_days or advance_notice_days is invalid")
        now = _now()
        task = {
            "id": str(uuid4()), "title": title.strip(), "description": payload.get("description") or None,
            "priority": priority, "due_at": due_at, "recurrence_days": recurrence,
            "advance_notice_days": notice, "completed_at": None,
            "created_at": _iso(now), "updated_at": _iso(now),
        }
        async with self._lock:
            self._data["tasks"].append(task)
            await self._async_save()
        return _present(task, now)

    async def async_update(self, task_id: str, changes: dict) -> dict:
        allowed = {"title", "description", "priority", "due_at", "recurrence_days", "advance_notice_days"}
        if not isinstance(changes, dict) or set(changes) - allowed:
            raise ValueError("update contains unsupported fields")
        async with self._lock:
            task = next((item for item in self._data["tasks"] if item["id"] == task_id), None)
            if task is None:
                raise KeyError(task_id)
            candidate = {**task, **changes}
            if not isinstance(candidate["title"], str) or not candidate["title"].strip():
                raise ValueError("title is required")
            if candidate["priority"] not in PRIORITIES:
                raise ValueError("priority is invalid")
            if type(candidate["recurrence_days"]) is not int or candidate["recurrence_days"] < 1:
                raise ValueError("recurrence_days is invalid")
            if type(candidate["advance_notice_days"]) is not int or candidate["advance_notice_days"] < 0:
                raise ValueError("advance_notice_days is invalid")
            candidate["title"] = candidate["title"].strip()
            candidate["due_at"] = _iso(_date(candidate["due_at"]))
            candidate["updated_at"] = _iso(_now())
            task.update(candidate)
            await self._async_save()
            return _present(task, _now())

    async def async_complete(self, task_id: str) -> dict:
        async with self._lock:
            task = next((item for item in self._data["tasks"] if item["id"] == task_id), None)
            if task is None:
                raise KeyError(task_id)
            now = _now()
            task["completed_at"] = _iso(now)
            task["due_at"] = _iso(now + timedelta(days=task["recurrence_days"]))
            task["updated_at"] = _iso(now)
            await self._async_save()
            return _present(task, now)

    async def async_delete(self, task_id: str) -> None:
        async with self._lock:
            before = len(self._data["tasks"])
            self._data["tasks"] = [task for task in self._data["tasks"] if task["id"] != task_id]
            if len(self._data["tasks"]) == before:
                raise KeyError(task_id)
            await self._async_save()
