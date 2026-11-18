#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -v
python3 -m compileall -q prototype demo.py custom_components/household_maintenance
node --check prototype/frontend/household-maintenance-panel.js
node --check prototype/frontend/household-maintenance-card.js
node --check custom_components/household_maintenance/frontend/panel.js
node --check custom_components/household_maintenance/frontend/household-maintenance-card.js
python3 - <<'PY'
import json
from pathlib import Path
root = Path('.')
manifest = json.loads((root / 'custom_components/household_maintenance/manifest.json').read_text())
hacs = json.loads((root / 'hacs.json').read_text())
assert manifest['domain'] == 'household_maintenance'
assert manifest['documentation'].startswith('https://github.com/')
assert manifest['issue_tracker'].startswith('https://github.com/')
assert hacs['name'] == 'Household Maintenance'
assert (root / 'LICENSE').is_file() and (root / 'assets/logo.svg').is_file()
print('HACS structure contract passed.')
PY
printf '\nVerification passed.\n'
