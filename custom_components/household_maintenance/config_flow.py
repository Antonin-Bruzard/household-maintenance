"""Minimal config flow placeholder for the local-only prototype."""
from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


class HouseholdMaintenanceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One local instance; production behaviour is intentionally out of scope."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Maintenance domestique", data={})
