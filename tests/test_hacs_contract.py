from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "household_maintenance"


class HacsContractTest(unittest.TestCase):
    def test_hacs_metadata_and_assets_are_present(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["domain"], "household_maintenance")
        self.assertEqual(manifest["name"], "Household Maintenance")
        self.assertTrue(manifest["documentation"].startswith("https://github.com/"))
        self.assertTrue(manifest["issue_tracker"].startswith("https://github.com/"))
        self.assertEqual(hacs["name"], "Household Maintenance")
        self.assertEqual(hacs["homeassistant"], "2024.7.0")
        self.assertEqual(len([path for path in (ROOT / "custom_components").iterdir() if path.is_dir()]), 1)
        self.assertTrue((ROOT / "LICENSE").is_file())
        self.assertTrue((ROOT / "assets" / "logo.svg").is_file())

    def test_runtime_uses_store_websocket_and_frontend_assets(self) -> None:
        init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        store = (COMPONENT / "store.py").read_text(encoding="utf-8")
        panel = (COMPONENT / "frontend" / "panel.js").read_text(encoding="utf-8")
        card = (COMPONENT / "frontend" / "household-maintenance-card.js").read_text(encoding="utf-8")

        self.assertIn("Store", store)
        self.assertIn("async_register_command", init)
        self.assertIn("connection.user.is_admin", init)
        self.assertIn("not_loaded", init)
        self.assertIn("hass.data.pop(DOMAIN", init)
        self.assertIn("async_register_panel", init)
        self.assertIn("async_register_static_paths", init)
        self.assertIn("callWS", panel)
        self.assertIn("household_maintenance/update", panel)
        self.assertIn("subscribeEvents", panel)
        self.assertIn("callWS", card)
        self.assertIn("customCards", card)

    def test_reads_are_authenticated_but_admin_is_reserved_for_mutations(self) -> None:
        init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        list_handler = init.split("async def websocket_list", 1)[1].split("async def _mutate", 1)[0]
        mutate_handler = init.split("async def _mutate", 1)[1].split("@websocket_api.websocket_command(_CREATE_SCHEMA)", 1)[0]

        self.assertNotIn("_require_admin(connection, msg)", list_handler)
        self.assertIn("_require_admin(connection, msg)", mutate_handler)


if __name__ == "__main__":
    unittest.main()
