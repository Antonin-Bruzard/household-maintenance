#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -v
python3 -m compileall -q prototype demo.py custom_components/household_maintenance
node --check prototype/frontend/household-maintenance-panel.js
node --check prototype/frontend/household-maintenance-card.js
node --check custom_components/household_maintenance/frontend/panel.js
printf '\nVerification passed.\n'
