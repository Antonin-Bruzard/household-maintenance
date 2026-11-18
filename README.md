# Household Maintenance

[![HACS validation](https://github.com/Antonin-Bruzard/household-maintenance/actions/workflows/validate.yml/badge.svg)](https://github.com/Antonin-Bruzard/household-maintenance/actions/workflows/validate.yml)

Local-first Home Assistant custom integration for recurring household-maintenance tasks. It stores only task metadata in Home Assistant's local `.storage`, exposes domain WebSocket commands, and provides a management panel plus a Lovelace summary card. No cloud service, analytics, equipment control, credential, or token is used.

![Household Maintenance logo](assets/logo.svg)

## Install with HACS

1. In **HACS → Integrations → ⋮ → Custom repositories**, add `Antonin-Bruzard/household-maintenance` with category **Integration**.
2. Install **Household Maintenance** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**, search for **Household Maintenance**, and complete the single local setup flow.
4. The **Maintenance** sidebar panel appears for Home Assistant administrators.

A GitHub Release is not required for a HACS custom repository. This integration is not submitted to the default HACS catalog.

## Lovelace card

Add the served JavaScript resource once in **Settings → Dashboards → Resources**:

```yaml
url: /household_maintenance/household-maintenance-card.js
type: module
```

Then use:

```yaml
type: custom:household-maintenance-card
limit: 3
```

The card is intentionally a priority summary: it shows overdue, due-today, critical, or high-priority tasks and navigates to the panel. Creation, changes, completion, and deletion remain in the administrator-only panel.

## WebSocket API

All commands use the authenticated Home Assistant WebSocket connection; mutations require an administrator.

- `household_maintenance/list` — optional `status` (`all`, `overdue`, `due_today`, `upcoming`, `scheduled`) and `sort` (`priority`, `due`)
- `household_maintenance/create` — `title`, timezone-aware ISO `due_at`, optional `description`, `priority`, `recurrence_days`, `advance_notice_days`
- `household_maintenance/update` — `task_id`, `changes`
- `household_maintenance/complete` — `task_id`, advances the due date by `recurrence_days`
- `household_maintenance/delete` — `task_id`

Each successful mutation emits `household_maintenance_updated`, which refreshes the panel and card.

## Development and verification

The repository keeps the initial isolated prototype under `prototype/`; the Home Assistant runtime does **not** use its JSON file or HTTP demo API. Runtime data is owned by `homeassistant.helpers.storage.Store` under the integration storage key.

```bash
bash verify.sh
```

The workflow validates repository structure, Python/JavaScript syntax and the legacy prototype regression tests. `.github/workflows/validate.yml` also runs Hassfest and HACS validation on GitHub.

For a disposable Home Assistant development instance, copy the repository's `custom_components/household_maintenance` directory into that instance's `config/custom_components/`, start Home Assistant, add the integration through Settings, create a task in the panel, restart the disposable instance, and confirm the task remains. Do not test against a production Home Assistant instance.

## License

MIT. See [LICENSE](LICENSE).
