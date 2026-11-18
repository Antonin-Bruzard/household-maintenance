class HouseholdMaintenanceCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; this.render(); }
  connectedCallback() { this.render(); }

  buildCard(message) {
    const card = document.createElement("ha-card");
    card.setAttribute("header", "Maintenance domestique");
    const content = document.createElement("div");
    content.className = "card-content";
    content.textContent = message;
    card.append(content);
    this.replaceChildren(card);
    return content;
  }

  async render() {
    const endpoint = this.config?.endpoint || "/api/household_maintenance/tasks?status=all&sort=priority";
    if (!endpoint.startsWith("/") || endpoint.startsWith("//")) {
      this.buildCard("Endpoint de synthèse invalide.");
      return;
    }
    this.buildCard("Chargement…");
    try {
      const response = await fetch(endpoint);
      const payload = await response.json();
      if (!response.ok || !Array.isArray(payload.tasks) || !payload.summary) throw new Error("Réponse invalide");
      const content = this.buildCard("");
      const counts = document.createElement("p");
      counts.textContent = `${payload.summary.overdue} en retard · ${payload.summary.due_today} aujourd’hui`;
      const list = document.createElement("ul");
      const prioritized = payload.tasks.slice(0, this.config?.limit || 3);
      if (prioritized.length === 0) {
        const row = document.createElement("li");
        row.textContent = "Aucune tâche prioritaire.";
        list.append(row);
      }
      for (const task of prioritized) {
        const row = document.createElement("li");
        row.textContent = `${task.title} — ${task.status} (${new Date(task.next_due_at).toLocaleDateString("fr-FR")})`;
        list.append(row);
      }
      const panel_url = typeof payload.summary.panel_url === "string" && payload.summary.panel_url.startsWith("/") && !payload.summary.panel_url.startsWith("//") ? payload.summary.panel_url : "/panel.html";
      const open = document.createElement("button");
      open.id = "open-panel";
      open.type = "button";
      open.textContent = "Ouvrir la gestion";
      open.addEventListener("click", () => window.location.assign(panel_url));
      content.append(counts, list, open);
    } catch (error) { this.buildCard("Synthèse indisponible."); }
  }

  getCardSize() { return 3; }
  static getStubConfig() { return { type: "custom:household-maintenance-card" }; }
}
customElements.define("household-maintenance-card", HouseholdMaintenanceCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "household-maintenance-card", name: "Maintenance domestique", description: "Synthèse et accès au panel, sans gestion de tâches." });
