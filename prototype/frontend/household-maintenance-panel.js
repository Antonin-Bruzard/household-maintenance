const API = "/api/household_maintenance/tasks";
const $ = (id) => document.getElementById(id);

function localIso(value) {
  return value.replace("+00:00", "Z").slice(0, 16);
}

async function call(path = "", options = {}) {
  const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Erreur API");
  return body;
}

function describe(task) {
  return `${task.criticality} · ${task.status} · échéance ${new Date(task.next_due_at).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" })}`;
}

async function render() {
  const status = $("status").value;
  const sort = $("sort").value;
  const result = await call(`?status=${encodeURIComponent(status)}&sort=${encodeURIComponent(sort)}`);
  $("summary").textContent = `${result.summary.overdue} en retard · ${result.summary.due_today} aujourd’hui · ${result.summary.upcoming} bientôt`;
  const tasks = $("tasks");
  tasks.replaceChildren(...result.tasks.map((task) => {
    const item = document.createElement("li");
    item.className = task.status;
    const title = document.createElement("strong"); title.textContent = task.title;
    const meta = document.createElement("span"); meta.className = "meta"; meta.textContent = describe(task);
    const edit = document.createElement("button"); edit.className = "secondary"; edit.textContent = "Modifier";
    edit.onclick = async () => { const titleValue = prompt("Titre", task.title); if (titleValue) { await call(`/${task.id}`, { method: "PATCH", body: JSON.stringify({ title: titleValue }) }); await render(); } };
    const complete = document.createElement("button"); complete.textContent = "Terminer";
    complete.onclick = async () => { await call(`/${task.id}/complete`, { method: "POST" }); await render(); };
    item.append(title, meta, edit, complete); return item;
  }));
}

$("refresh").onclick = () => render().catch(showError);
$("status").onchange = () => render().catch(showError);
$("sort").onchange = () => render().catch(showError);
$("create").onsubmit = async (event) => {
  event.preventDefault(); const form = new FormData(event.currentTarget);
  const due = new Date(form.get("due_at"));
  try { await call("", { method: "POST", body: JSON.stringify({ title: form.get("title"), due_at: due.toISOString(), criticality: form.get("criticality"), recurrence_days: Number(form.get("recurrence_days")) }) }); event.currentTarget.reset(); await render(); showNotice("Tâche créée."); } catch (error) { showError(error); }
};
function showNotice(message) { $("notice").textContent = message; }
function showError(error) { $("notice").textContent = error.message; $("notice").style.color = "#fca5a5"; }
render().catch(showError);
