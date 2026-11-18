from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "household_maintenance"
FRONTEND = ROOT / "prototype" / "frontend"


class ScaffoldContractTest(unittest.TestCase):
    def test_home_assistant_scaffold_declares_the_provisional_domain_and_panel(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")

        self.assertEqual(manifest["domain"], "household_maintenance")
        self.assertIn("async_register_panel", init)
        self.assertIn("PANEL_URL", init)

    def test_card_is_summary_only_and_routes_to_the_panel(self) -> None:
        card = (FRONTEND / "household-maintenance-card.js").read_text(encoding="utf-8")

        self.assertIn("panel_url", card)
        self.assertIn("window.location.assign", card)
        self.assertIn("textContent", card)
        self.assertNotIn("innerHTML", card)
        self.assertNotIn('method: "POST"', card)
        self.assertNotIn('method: "PATCH"', card)


if __name__ == "__main__":
    unittest.main()
