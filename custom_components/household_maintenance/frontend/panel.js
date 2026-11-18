// HA scaffold asset: registers the panel shell. The local functional panel is
// prototype/frontend/household-maintenance-panel.js and uses the same API contract.
class HouseholdMaintenancePanel extends HTMLElement {
  set hass(value) { this._hass = value; this.render(); }
  connectedCallback() { this.render(); }
  render() {
    this.innerHTML = `<ha-card header="Maintenance domestique"><div class="card-content">Prototype local : la gestion complète est démontrée par le panel local. Ce scaffold attend le futur adaptateur WebSocket Home Assistant.</div></ha-card>`;
  }
}
customElements.define("household-maintenance-panel", HouseholdMaintenancePanel);
