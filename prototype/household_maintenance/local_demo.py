from __future__ import annotations

import json
import mimetypes
import threading
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .store import MaintenanceStore

ROOT = Path(__file__).resolve().parent.parent / "frontend"
FIXED_NOW = datetime(2026, 11, 18, 12, tzinfo=UTC)


class LocalDemoServer:
    """Ephemeral local HTTP server used only by the workspace demonstration/tests."""

    def __init__(self, storage_path: Path, port: int = 0) -> None:
        self.store = MaintenanceStore.open(storage_path)
        self.store.seed_demo(now=FIXED_NOW)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def _handler(self):
        store = self.store

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:
                return

            def _json(self, status: int, body: dict) -> None:
                payload = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                return json.loads(raw.decode("utf-8")) if raw else {}

            def _summary(self) -> dict:
                tasks = store.list_tasks(now=FIXED_NOW)
                return {
                    "overdue": sum(task["status"] == "overdue" for task in tasks),
                    "due_today": sum(task["status"] == "due_today" for task in tasks),
                    "upcoming": sum(task["status"] == "upcoming" for task in tasks),
                    "total": len(tasks),
                    "panel_url": "/panel.html",
                }

            def _static(self, path: str) -> None:
                relative = "panel.html" if path == "/" else path.lstrip("/")
                target = (ROOT / relative).resolve()
                if ROOT not in target.parents and target != ROOT:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                if not target.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                content = target.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/health":
                    self._json(HTTPStatus.OK, {"status": "ok", "storage_version": store.snapshot()["version"]})
                    return
                if parsed.path == "/api/household_maintenance/tasks":
                    query = parse_qs(parsed.query)
                    try:
                        tasks = store.list_tasks(
                            status=query.get("status", ["all"])[0],
                            sort=query.get("sort", ["priority"])[0],
                            now=FIXED_NOW,
                        )
                    except ValueError as error:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                        return
                    self._json(HTTPStatus.OK, {"version": 1, "tasks": tasks, "summary": self._summary()})
                    return
                self._static(parsed.path)

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                try:
                    body = self._body()
                    if parsed.path == "/api/household_maintenance/tasks":
                        task = store.create(now=FIXED_NOW, **body)
                        self._json(HTTPStatus.CREATED, {"task": task, "summary": self._summary()})
                        return
                    prefix = "/api/household_maintenance/tasks/"
                    if parsed.path.startswith(prefix) and parsed.path.endswith("/complete"):
                        task_id = parsed.path[len(prefix):-len("/complete")].rstrip("/")
                        task = store.complete(task_id, now=FIXED_NOW)
                        self._json(HTTPStatus.OK, {"task": task, "summary": self._summary()})
                        return
                    self._json(HTTPStatus.NOT_FOUND, {"error": "Route inconnue"})
                except (ValueError, KeyError, json.JSONDecodeError, TypeError) as error:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

            def do_PATCH(self) -> None:
                parsed = urlparse(self.path)
                prefix = "/api/household_maintenance/tasks/"
                if not parsed.path.startswith(prefix):
                    self._json(HTTPStatus.NOT_FOUND, {"error": "Route inconnue"})
                    return
                try:
                    task_id = parsed.path[len(prefix):]
                    task = store.update(task_id, self._body(), now=FIXED_NOW)
                    self._json(HTTPStatus.OK, {"task": task, "summary": self._summary()})
                except (ValueError, KeyError, json.JSONDecodeError, TypeError) as error:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

        return Handler

    def __enter__(self) -> "LocalDemoServer":
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
