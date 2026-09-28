let allServices = [];

async function fetchServices() {
  const res = await fetch("/services");
  if (!res.ok) throw new Error("Impossible de charger les services");
  return res.json();
}

async function createService(name, url) {
  const res = await fetch("/services", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, url }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Erreur lors de la création");
  }
  return res.json();
}

async function checkService(id) {
  const res = await fetch(`/services/${id}/check`, { method: "POST" });
  if (!res.ok) throw new Error("Erreur lors du check");
  return res.json();
}

async function deleteService(id) {
  const res = await fetch(`/services/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error("Erreur lors de la suppression");
}

function statusBadge(check) {
  if (!check) return `<span class="badge unknown">Jamais vérifié</span>`;
  const cls = check.status === "UP" ? "up" : "down";
  return `<span class="badge ${cls}">${check.status}</span>`;
}

function formatLatency(check) {
  if (!check || check.response_time_ms == null) return "—";
  return `${Math.round(check.response_time_ms)} ms`;
}

function formatDate(check) {
  if (!check) return "—";
  return new Date(check.checked_at).toLocaleString("fr-FR");
}

function formatAvailability(pct) {
  return pct == null ? "—" : `${pct}%`;
}

// Small inline SVG line chart of recent latencies — no charting library needed.
function sparkline(values) {
  const clean = values.filter((v) => v != null);
  if (clean.length < 2) return "";

  const w = 60;
  const h = 20;
  const pad = 2;
  const max = Math.max(...clean);
  const min = Math.min(...clean);
  const range = max - min || 1;
  const stepX = (w - pad * 2) / (clean.length - 1);

  const points = clean
    .map((v, i) => {
      const x = pad + i * stepX;
      const y = h - pad - ((v - min) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return `<svg class="sparkline" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${points}" /></svg>`;
}

function renderStats(services) {
  const total = services.length;
  const up = services.filter((s) => s.last_check?.status === "UP").length;
  const down = services.filter((s) => s.last_check?.status === "DOWN").length;
  document.getElementById("stat-total").textContent = total;
  document.getElementById("stat-up").textContent = up;
  document.getElementById("stat-down").textContent = down;
}

function renderTable(services) {
  const tbody = document.getElementById("services-body");
  if (services.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty">Aucun service ne correspond.</td></tr>`;
    return;
  }

  tbody.innerHTML = services
    .map((s) => {
      const latencies = (s.recent_checks || []).map((c) => c.response_time_ms);
      return `
    <tr>
      <td>${s.name}</td>
      <td><a href="${s.url}" target="_blank" rel="noopener">${s.url}</a></td>
      <td>${statusBadge(s.last_check)}</td>
      <td>${formatAvailability(s.availability_percent)}</td>
      <td class="latency-cell">
        <span>${formatLatency(s.last_check)}</span>
        ${sparkline(latencies)}
      </td>
      <td>${formatDate(s.last_check)}</td>
      <td class="row-actions">
        <button class="secondary" data-check="${s.id}">Vérifier</button>
        <button class="secondary" data-delete="${s.id}">Supprimer</button>
      </td>
    </tr>`;
    })
    .join("");
}

function applyFilter() {
  const query = document.getElementById("search-input").value.trim().toLowerCase();
  const filtered = query ? allServices.filter((s) => s.name.toLowerCase().includes(query)) : allServices;
  renderTable(filtered);
}

async function refresh() {
  try {
    allServices = await fetchServices();
    renderStats(allServices);
    applyFilter();
  } catch (e) {
    console.error(e);
  }
}

document.getElementById("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("input-name").value.trim();
  const url = document.getElementById("input-url").value.trim();
  const errorEl = document.getElementById("form-error");
  errorEl.textContent = "";
  try {
    await createService(name, url);
    e.target.reset();
    await refresh();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("refresh-btn").addEventListener("click", refresh);
document.getElementById("search-input").addEventListener("input", applyFilter);

document.getElementById("services-body").addEventListener("click", async (e) => {
  const checkId = e.target.getAttribute("data-check");
  const deleteId = e.target.getAttribute("data-delete");

  if (checkId) {
    e.target.disabled = true;
    e.target.textContent = "...";
    try {
      await checkService(checkId);
      await refresh();
    } catch (err) {
      alert(err.message);
    }
  }

  if (deleteId) {
    if (!confirm("Supprimer ce service ?")) return;
    try {
      await deleteService(deleteId);
      await refresh();
    } catch (err) {
      alert(err.message);
    }
  }
});

refresh();
setInterval(refresh, 15000);
