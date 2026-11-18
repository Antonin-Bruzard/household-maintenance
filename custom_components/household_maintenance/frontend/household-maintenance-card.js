class HouseholdMaintenanceCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; }
  set hass(value) { this._hass = value; this._subscribe(); this._refresh(); }
  connectedCallback() { this._refresh(); }
  disconnectedCallback() { if (this._unsubscribe) this._unsubscribe(); }
  _subscribe() { if (!this._hass || this._unsubscribe) return; this._hass.connection.subscribeEvents(() => this._refresh(), "household_maintenance_updated").then((unsub) => { this._unsubscribe = unsub; }); }
  async _refresh() { if (!this._hass) return; try { this._tasks=(await this._hass.callWS({type:"household_maintenance/list",status:"all",sort:"priority"})).tasks; this._render(); } catch (_) { this._tasks=[]; this._render("Synthèse indisponible."); } }
  _render(error="") { const card=document.createElement("ha-card");card.header="Maintenance";const body=document.createElement("div");body.className="card-content";const important=(this._tasks||[]).filter(t=>["critical","high"].includes(t.priority)||["overdue","due_today"].includes(t.status)).slice(0,Number(this.config?.limit||3)); const summary=document.createElement("p");summary.textContent=error||`${important.length} élément(s) important(s)`;body.append(summary);const list=document.createElement("ul");for(const task of important){const row=document.createElement("li");row.textContent=`${task.title} — ${task.status}`;list.append(row)}if(!important.length&&!error){const row=document.createElement("li");row.textContent="Aucune tâche prioritaire.";list.append(row)}body.append(list);const open=document.createElement("button");open.type="button";open.textContent="Ouvrir la gestion";open.onclick=()=>this._hass.navigate("household-maintenance");body.append(open);card.append(body);this.replaceChildren(card); }
  getCardSize() { return 3; }
  static getStubConfig() { return {type:"custom:household-maintenance-card"}; }
}
customElements.define("household-maintenance-card", HouseholdMaintenanceCard);
window.customCards=window.customCards||[];
window.customCards.push({type:"household-maintenance-card",name:"Household Maintenance",description:"Priorités de maintenance et accès au panel."});
