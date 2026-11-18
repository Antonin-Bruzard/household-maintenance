"""Home Assistant entry point for the isolated prototype scaffold.

This module is deliberately not installed or loaded by this task. The functional
surface is demonstrated by prototype.household_maintenance.local_demo instead.
"""
from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PANEL_COMPONENT, PANEL_ICON, PANEL_TITLE, PANEL_URL


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register only local frontend assets and the management panel."""
    frontend_root = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [
            frontend.StaticPathConfig(
                PANEL_URL,
                str(frontend_root / "panel.js"),
                cache_headers=False,
            )
        ]
    )
    panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_COMPONENT,
        frontend_url=PANEL_URL,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={"domain": DOMAIN},
    )
    return True
