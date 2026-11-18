#!/usr/bin/env python3
"""Exercise Household Maintenance against a disposable Home Assistant Core.

The workflow starts an isolated container with this repository copied to
/config/custom_components. This script onboards an administrator locally,
uses Home Assistant's authenticated WebSocket API, and proves persistence
across a container restart. It deliberately prints no bearer token.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, NoReturn

import websocket  # type: ignore[import-not-found]

BASE_URL = os.environ.get("HA_URL", "http://127.0.0.1:8123")
WS_URL = BASE_URL.replace("http://", "ws://", 1).replace("https://", "wss://", 1) + "/api/websocket"
CLIENT_ID = f"{BASE_URL}/"
CONFIG_DIR = Path(os.environ.get("HA_CONFIG", ".ha-config"))
CONTAINER = os.environ.get("HA_CONTAINER", "household-maintenance-ci")


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def request_json(path: str, payload: dict[str, Any] | None = None, token: str | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        fail(f"HTTP {exc.code} for {path}: {detail}")


def request_form(path: str, values: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=urllib.parse.urlencode(values).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        fail(f"Token exchange failed: HTTP {exc.code}: {exc.read().decode(errors='replace')}")


def get_text(path: str, token: str) -> str:
    request = urllib.request.Request(f"{BASE_URL}{path}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                fail(f"Unexpected status {response.status} for {path}")
            return response.read().decode()
    except urllib.error.HTTPError as exc:
        fail(f"Static resource unavailable at {path}: HTTP {exc.code}")


def wait_for_home_assistant() -> None:
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(f"{BASE_URL}/api/onboarding")
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status == 200:
                    print("Home Assistant API is ready.")
                    return
        except (OSError, urllib.error.URLError, TimeoutError):
            time.sleep(2)
    fail("Home Assistant did not become ready within five minutes")


def onboard_admin() -> str:
    user = request_json(
        "/api/onboarding/users",
        {
            "client_id": CLIENT_ID,
            "name": "CI Administrator",
            "username": "ci-admin",
            "password": "ci-only-password-not-a-secret",
            "language": "en",
        },
    )
    auth_code = user.get("auth_code")
    if not isinstance(auth_code, str) or not auth_code:
        fail("Onboarding did not return an authorization code")
    token_response = request_form(
        "/auth/token",
        {"client_id": CLIENT_ID, "grant_type": "authorization_code", "code": auth_code},
    )
    token = token_response.get("access_token")
    if not isinstance(token, str) or not token:
        fail("Onboarding token exchange did not return an access token")
    # Complete the core-config onboarding stage so this is a normal initialized
    # Core instance, while deliberately leaving all optional cloud features off.
    request_json("/api/onboarding/core_config", {}, token)
    print("Created a local disposable Home Assistant administrator.")
    return token


class HomeAssistantWebSocket:
    def __init__(self, token: str) -> None:
        self._socket = websocket.create_connection(WS_URL, timeout=20)
        greeting = self._recv()
        if greeting.get("type") != "auth_required":
            fail(f"Expected auth_required, got {greeting}")
        self._send({"type": "auth", "access_token": token})
        authenticated = self._recv()
        if authenticated.get("type") != "auth_ok":
            fail(f"WebSocket authentication failed: {authenticated}")
        self._next_id = 1
        self.events: list[dict[str, Any]] = []

    def close(self) -> None:
        self._socket.close()

    def _send(self, payload: dict[str, Any]) -> None:
        self._socket.send(json.dumps(payload))

    def _recv(self) -> dict[str, Any]:
        return json.loads(self._socket.recv())

    def call(self, command: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"id": request_id, **command})
        while True:
            message = self._recv()
            if message.get("type") == "event":
                self.events.append(message)
                continue
            if message.get("id") != request_id:
                continue
            if not message.get("success"):
                fail(f"WebSocket command {command['type']} failed: {message}")
            return message.get("result", {})

    def wait_for_event(self, event_type: str, timeout: float = 10) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in self.events:
                if event.get("event", {}).get("event_type") == event_type:
                    return
            self._socket.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                message = self._recv()
            except websocket.WebSocketTimeoutException:
                break
            if message.get("type") == "event":
                self.events.append(message)
        fail(f"Did not receive {event_type} after mutation")


def wait_for_integration(ws: HomeAssistantWebSocket) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        request_id = ws._next_id
        ws._next_id += 1
        ws._send({"id": request_id, "type": "household_maintenance/list", "status": "all", "sort": "priority"})
        while True:
            message = ws._recv()
            if message.get("type") == "event":
                ws.events.append(message)
                continue
            if message.get("id") != request_id:
                continue
            if message.get("success"):
                print("Integration loaded and WebSocket commands are available.")
                return
            if message.get("error", {}).get("code") != "not_loaded":
                fail(f"Integration failed while setting up: {message}")
            time.sleep(1)
            break
    fail("Integration did not load after its config flow completed")


def configure_integration(ws: HomeAssistantWebSocket) -> None:
    result = ws.call({"type": "config_entries/flow", "handler": "household_maintenance", "show_advanced_options": False})
    if result.get("type") != "create_entry":
        fail(f"Config flow did not create the local entry: {result}")
    wait_for_integration(ws)


def assert_static_assets(token: str) -> None:
    panel = get_text("/household_maintenance/panel.js", token)
    card = get_text("/household_maintenance/household-maintenance-card.js", token)
    if "customElements.define(\"household-maintenance-panel\"" not in panel:
        fail("Management panel resource is not the expected web component")
    if "window.customCards" not in card or "household-maintenance-card" not in card:
        fail("Lovelace card resource is not declared as a custom card")
    print("Panel and Lovelace card resources are served by Home Assistant.")


def exercise_crud_and_persistence(token: str) -> None:
    ws = HomeAssistantWebSocket(token)
    try:
        ws.call({"type": "subscribe_events", "event_type": "household_maintenance_updated"})
        configure_integration(ws)
        assert_static_assets(token)

        invalid_id = ws._next_id
        ws._next_id += 1
        ws._send({"id": invalid_id, "type": "household_maintenance/create", "title": "Invalid", "due_at": "not-a-date"})
        while True:
            invalid = ws._recv()
            if invalid.get("id") == invalid_id:
                break
        if invalid.get("success") or invalid.get("error", {}).get("code") != "invalid_task":
            fail(f"Invalid CRUD input did not return a clear error: {invalid}")

        created = ws.call(
            {
                "type": "household_maintenance/create",
                "title": "Replace kitchen smoke detector battery",
                "description": "CI runtime proof",
                "due_at": "2030-01-02T09:30:00+00:00",
                "priority": "high",
                "recurrence_days": 365,
                "advance_notice_days": 14,
            }
        )
        task_id = created.get("id")
        if not isinstance(task_id, str):
            fail(f"Create response has no task id: {created}")
        ws.wait_for_event("household_maintenance_updated")

        updated = ws.call(
            {
                "type": "household_maintenance/update",
                "task_id": task_id,
                "changes": {"title": "Replace smoke detector battery", "priority": "critical"},
            }
        )
        if updated.get("title") != "Replace smoke detector battery" or updated.get("priority") != "critical":
            fail(f"Update did not persist expected fields: {updated}")

        completed = ws.call({"type": "household_maintenance/complete", "task_id": task_id})
        if not completed.get("completed_at"):
            fail(f"Completion did not record completion history: {completed}")
        ws.wait_for_event("household_maintenance_updated")
    finally:
        ws.close()

    storage = CONFIG_DIR / ".storage" / "household_maintenance.tasks"
    deadline = time.monotonic() + 30
    while not storage.is_file() and time.monotonic() < deadline:
        time.sleep(1)
    if not storage.is_file():
        fail("Home Assistant Store file was not written after CRUD")
    print("CRUD commands, events, and Home Assistant Store write succeeded.")

    subprocess.run(["docker", "restart", CONTAINER], check=True, stdout=subprocess.DEVNULL)
    wait_for_home_assistant()

    persisted = HomeAssistantWebSocket(token)
    try:
        tasks = persisted.call({"type": "household_maintenance/list", "status": "all", "sort": "priority"}).get("tasks", [])
        matching = [task for task in tasks if task.get("title") == "Replace smoke detector battery"]
        if len(matching) != 1 or not matching[0].get("completed_at"):
            fail(f"Task was not restored from Store after restart: {tasks}")
        task_id = matching[0]["id"]
        persisted.call({"type": "household_maintenance/delete", "task_id": task_id})
        remaining = persisted.call({"type": "household_maintenance/list", "status": "all", "sort": "priority"}).get("tasks", [])
        if any(task.get("id") == task_id for task in remaining):
            fail("Delete did not remove the task")
    finally:
        persisted.close()
    print("Persistence survived restart; delete operation also succeeded.")


def main() -> int:
    wait_for_home_assistant()
    token = onboard_admin()
    exercise_crud_and_persistence(token)
    print("Home Assistant runtime verification passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Home Assistant runtime verification failed: {exc}", file=sys.stderr)
        raise
