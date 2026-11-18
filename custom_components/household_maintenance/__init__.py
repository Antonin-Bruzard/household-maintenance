"""Home Assistant entry point for the local Household Maintenance integration."""
from __future__ import annotations

from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CARD_URL, DATA_STORE, DOMAIN, EVENT_UPDATED, PANEL_COMPONENT, PANEL_ICON, PANEL_TITLE, PANEL_URL
from .store import MaintenanceStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LIST_SCHEMA = vol.Schema({vol.Required("type"): f"{DOMAIN}/list", vol.Optional("status", default="all"): vol.In(["all", "overdue", "due_today", "upcoming", "scheduled"]), vol.Optional("sort", default="priority"): vol.In(["priority", "due"])})
_CREATE_SCHEMA = vol.Schema({vol.Required("type"): f"{DOMAIN}/create", vol.Required("title"): str, vol.Required("due_at"): str, vol.Optional("description"): vol.Any(str, None), vol.Optional("priority", default="normal"): vol.In(["critical", "high", "normal", "low"]), vol.Optional("recurrence_days", default=30): int, vol.Optional("advance_notice_days", default=7): int})
_UPDATE_SCHEMA = vol.Schema({vol.Required("type"): f"{DOMAIN}/update", vol.Required("task_id"): str, vol.Required("changes"): dict})
_TASK_SCHEMA = vol.Schema({vol.Required("type"): vol.In([f"{DOMAIN}/complete", f"{DOMAIN}/delete"]), vol.Required("task_id"): str})


def _store(hass: HomeAssistant) -> MaintenanceStore:
    return hass.data[DOMAIN][DATA_STORE]


def _runtime_is_available(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> bool:
    if DOMAIN in hass.data:
        return True
    connection.send_error(msg["id"], "not_loaded", "Household Maintenance is not configured")
    return False


def _require_admin(connection: websocket_api.ActiveConnection, msg: dict) -> bool:
    if connection.user.is_admin:
        return True
    connection.send_error(msg["id"], "unauthorized", "Administrator permission is required")
    return False


def _send_exception(connection: websocket_api.ActiveConnection, msg: dict, exc: Exception) -> None:
    code = "not_found" if isinstance(exc, KeyError) else "invalid_task"
    connection.send_error(msg["id"], code, str(exc).strip("'"))


@websocket_api.websocket_command(_LIST_SCHEMA)
@websocket_api.async_response
async def websocket_list(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the safe task projection for panels and Lovelace cards."""
    if not _runtime_is_available(hass, connection, msg) or not _require_admin(connection, msg):
        return
    try:
        connection.send_result(msg["id"], {"tasks": await _store(hass).async_list(msg["status"], msg["sort"]), "panel_path": "household-maintenance"})
    except ValueError as exc:
        _send_exception(connection, msg, exc)


async def _mutate(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict, operation: str) -> None:
    if not _runtime_is_available(hass, connection, msg) or not _require_admin(connection, msg):
        return
    try:
        store = _store(hass)
        if operation == "create":
            result = await store.async_create(msg)
        elif operation == "update":
            result = await store.async_update(msg["task_id"], msg["changes"])
        elif operation == "complete":
            result = await store.async_complete(msg["task_id"])
        else:
            await store.async_delete(msg["task_id"])
            result = {"task_id": msg["task_id"]}
        hass.bus.async_fire(EVENT_UPDATED)
        connection.send_result(msg["id"], result)
    except (KeyError, ValueError) as exc:
        _send_exception(connection, msg, exc)


@websocket_api.websocket_command(_CREATE_SCHEMA)
@websocket_api.async_response
async def websocket_create(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    await _mutate(hass, connection, msg, "create")


@websocket_api.websocket_command(_UPDATE_SCHEMA)
@websocket_api.async_response
async def websocket_update(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    await _mutate(hass, connection, msg, "update")


@websocket_api.websocket_command(_TASK_SCHEMA)
@websocket_api.async_response
async def websocket_task(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    await _mutate(hass, connection, msg, msg["type"].rsplit("/", 1)[1])


async def _async_setup_runtime(hass: HomeAssistant) -> None:
    if DOMAIN in hass.data:
        return
    root = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths([
        frontend.StaticPathConfig(PANEL_URL, str(root / "panel.js"), cache_headers=False),
        frontend.StaticPathConfig(CARD_URL, str(root / "household-maintenance-card.js"), cache_headers=False),
    ])
    panel_custom.async_register_panel(hass, webcomponent_name=PANEL_COMPONENT, frontend_url=PANEL_URL, sidebar_title=PANEL_TITLE, sidebar_icon=PANEL_ICON, require_admin=True, config={"domain": DOMAIN})
    store = MaintenanceStore(hass)
    await store.async_load()
    hass.data[DOMAIN] = {DATA_STORE: store}
    websocket_api.async_register_command(hass, websocket_list)
    websocket_api.async_register_command(hass, websocket_create)
    websocket_api.async_register_command(hass, websocket_update)
    websocket_api.async_register_command(hass, websocket_task)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Declare configuration validation for the config-entry integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure the single local task store through the UI integration flow."""
    await _async_setup_runtime(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.pop(DOMAIN, None)
    return True
