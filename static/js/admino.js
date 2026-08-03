const state = {
  user: null,
  activeView: "overview",
  businesses: [],
  adminos: [],
  logs: [],
  bizSort: { key: "created_at", dir: "desc" },
};

let csrfToken = "";

const titles = {
  overview: "Platform Overview",
  businesses: "All Businesses",
  logs: "Audit Logs",
  adminos: "Admino Accounts",
};

function qs(selector) {
  return document.querySelector(selector);
}

function qsa(selector) {
  return Array.from(document.querySelectorAll(selector));
}

function getCookie(name) {
  return document.cookie.split('; ').reduce((acc, cookie) => {
    const index = cookie.indexOf('=');
    const key = index < 0 ? cookie : cookie.slice(0, index);
    const value = index < 0 ? '' : cookie.slice(index + 1);
    return key === name ? decodeURIComponent(value) : acc;
  }, '');
}

function getToken() {
  const stored = localStorage.getItem("token");
  if (stored) {
    try {
      const decoded = JSON.parse(atob(stored.split('.')[1]));
      if (decoded.exp * 1000 > Date.now()) {
        return stored;
      }
    } catch (err) {
      // fall back to cookie
    }
  }
  const cookieToken = getCookie("token");
  if (cookieToken) {
    localStorage.setItem("token", cookieToken);
    return cookieToken;
  }
  return null;
}

function decodeToken() {
  const token = getToken();
  if (!token) return null;
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch (err) {
    return null;
  }
}

async function loadCsrfToken() {
  try {
    const res = await fetch('/csrf-token', { credentials: 'same-origin' });
    if (!res.ok) return;
    const data = await res.json();
    csrfToken = data.csrf_token || '';
  } catch (err) {
    console.warn('Failed to load CSRF token', err);
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function jsArg(value) {
  return escapeHtml(JSON.stringify(String(value ?? "")));
}

function dateOnly(value) {
  return value ? String(value).slice(0, 10) : "-";
}

function emptyRow(message, span = 5) {
  return `<tr><td colspan="${span}"><div class="empty">${escapeHtml(message)}</div></td></tr>`;
}

function emptyBlock(message, actionLabel = "", action = "") {
  return `
    <div class="empty">
      <div>${escapeHtml(message)}</div>
      ${actionLabel ? `<button class="btn-secondary" type="button" onclick="${action}">${escapeHtml(actionLabel)}</button>` : ""}
    </div>
  `;
}

function setAlert(id, message, type) {
  const el = qs(`#${id}`);
  if (!el) return;
  el.textContent = message || "";
  el.className = message ? `alert ${type}` : "alert";
}

function toast(message, type = "success") {
  const area = qs("#toastArea");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  area.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

async function api(url, opts = {}) {
  opts.credentials = "same-origin";
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    "X-CSRF-Token": csrfToken,
    ...(opts.headers || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(url, { ...opts, headers });
  } catch (err) {
    throw new Error("Network error. Check the server and try again.");
  }

  let data = {};
  try {
    data = await res.json();
  } catch (err) {
    data = {};
  }

  if (res.status === 401 || res.status === 403) {
    localStorage.removeItem("token");
    toast("Session expired. Please sign in again.", "error");
    setTimeout(() => { window.location.href = "/"; }, 800);
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    throw new Error(data.msg || `Request failed (${res.status})`);
  }

  return data;
}

function logout() {
  localStorage.removeItem("token");
  document.cookie = "token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  window.location.href = "/";
}

function confirmAction({ title, message, confirmText, okText = "Confirm", requireReason = false }) {
  const modal = qs("#confirmModal");
  const input = qs("#confirmTypeInput");
  const reason = qs("#confirmReasonInput");
  const field = qs("#confirmTypeField");
  const reasonField = qs("#confirmReasonField");
  const ok = qs("#confirmOk");
  const cancel = qs("#confirmCancel");

  qs("#confirmTitle").textContent = title;
  qs("#confirmMessage").textContent = message;
  ok.textContent = okText;
  input.value = "";
  reason.value = "";
  reasonField.hidden = !requireReason;

  if (confirmText) {
    field.hidden = false;
    qs("#confirmTypeLabel").textContent = `Type "${confirmText}" to confirm`;
    ok.disabled = true;
  } else {
    field.hidden = true;
    ok.disabled = requireReason;
  }

  modal.hidden = false;
  if (confirmText) input.focus();

  return new Promise((resolve) => {
    function cleanup(result) {
      modal.hidden = true;
      input.removeEventListener("input", validate);
      reason.removeEventListener("input", validate);
      ok.removeEventListener("click", onOk);
      cancel.removeEventListener("click", onCancel);
      modal.removeEventListener("click", onBackdrop);
      resolve(result);
    }

    function validate() {
      const typedOk = !confirmText || input.value === confirmText;
      const reasonOk = !requireReason || reason.value.trim().length >= 3;
      ok.disabled = !typedOk || !reasonOk;
    }

    function onOk() {
      cleanup({ confirmed: true, reason: reason.value.trim() });
    }

    function onCancel() {
      cleanup({ confirmed: false, reason: "" });
    }

    function onBackdrop(event) {
      if (event.target === modal) cleanup(false);
    }

    input.addEventListener("input", validate);
    reason.addEventListener("input", validate);
    ok.addEventListener("click", onOk);
    cancel.addEventListener("click", onCancel);
    modal.addEventListener("click", onBackdrop);
  });
}

function updateUrlState() {
  const params = new URLSearchParams();
  if (state.activeView !== "overview") params.set("view", state.activeView);
  if (qs("#bizSearch")?.value) params.set("biz_q", qs("#bizSearch").value.trim());
  if (qs("#bizStatusFilter")?.value && qs("#bizStatusFilter").value !== "all") params.set("biz_status", qs("#bizStatusFilter").value);
  if (qs("#adminoSearch")?.value) params.set("admino_q", qs("#adminoSearch").value.trim());
  if (qs("#logBizFilter")?.value) params.set("log_biz", qs("#logBizFilter").value.trim());
  if (qs("#logActionFilter")?.value) params.set("log_action", qs("#logActionFilter").value.trim());
  const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
  window.history.replaceState(null, "", next);
}

function restoreUrlState() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("biz_q")) qs("#bizSearch").value = params.get("biz_q");
  if (params.get("biz_status")) qs("#bizStatusFilter").value = params.get("biz_status");
  if (params.get("admino_q")) qs("#adminoSearch").value = params.get("admino_q");
  if (params.get("log_biz")) qs("#logBizFilter").value = params.get("log_biz");
  if (params.get("log_action")) qs("#logActionFilter").value = params.get("log_action");
  return params.get("view") || "overview";
}

function showView(name) {
  state.activeView = name;
  qsa(".view").forEach((view) => view.classList.remove("active"));
  qsa(".nav-item").forEach((item) => item.classList.remove("active"));
  qs(`#view-${name}`).classList.add("active");
  const nav = qs(`#nav-${name}`);
  if (nav) nav.classList.add("active");
  qs("#pageTitle").textContent = titles[name] || name;

  if (name === "overview") loadStats();
  if (name === "businesses") loadBusinesses();
  updateUrlState();
  if (name === "adminos") loadAdminos();
  if (name === "logs") loadLogs();
}

function refreshActiveView() {
  if (state.activeView === "logs") {
    loadLogs();
  } else {
    showView(state.activeView);
  }
}

async function loadStats() {
  try {
    const data = await api("/api/admino/stats");
    qs("#st-biz").textContent = data.total_businesses ?? "-";
    qs("#st-active").textContent = data.active_businesses ?? "-";
    qs("#st-users").textContent = data.total_users ?? "-";
    qs("#st-adminos").textContent = data.total_adminos ?? "-";
  } catch (err) {
    toast(err.message, "error");
  }
}

async function loadBusinesses() {
  const tbody = qs("#bizTable");
  tbody.innerHTML = emptyRow("Loading...");
  try {
    const data = await api("/api/admino/businesses");
    state.businesses = data.businesses || [];
    updateBusinessOptions();
    renderBusinesses();
  } catch (err) {
    tbody.innerHTML = emptyRow(err.message);
    toast(err.message, "error");
  }
}

function filteredBusinesses() {
  const query = qs("#bizSearch").value.trim().toLowerCase();
  const status = qs("#bizStatusFilter").value;
  const filtered = state.businesses.filter((business) => {
    const active = business.active !== false;
    const matchesStatus = status === "all" || (status === "active" && active) || (status === "suspended" && !active);
    const haystack = `${business.business_id || ""} ${business.company_name || ""}`.toLowerCase();
    return matchesStatus && (!query || haystack.includes(query));
  });

  const { key, dir } = state.bizSort;
  return filtered.sort((a, b) => {
    const av = key === "active" ? (a.active !== false ? 1 : 0) : String(a[key] || "").toLowerCase();
    const bv = key === "active" ? (b.active !== false ? 1 : 0) : String(b[key] || "").toLowerCase();
    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });
}

function renderBusinesses() {
  const tbody = qs("#bizTable");
  const list = filteredBusinesses();
  qs("#businessCount").textContent = `${list.length} of ${state.businesses.length} businesses shown`;
  qsa("[data-biz-sort]").forEach((button) => {
    button.classList.toggle("active", button.dataset.bizSort === state.bizSort.key);
    button.classList.toggle("asc", button.dataset.bizSort === state.bizSort.key && state.bizSort.dir === "asc");
    button.classList.toggle("desc", button.dataset.bizSort === state.bizSort.key && state.bizSort.dir === "desc");
  });

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="5">${emptyBlock("No businesses match the current filters.", "Reset filters", "resetBusinessFilters()")}</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map((business) => {
    const id = escapeHtml(business.business_id);
    const name = escapeHtml(business.company_name || "Untitled business");
    const active = business.active !== false;
    return `
      <tr>
        <td><span class="code">${id}</span></td>
        <td><strong>${name}</strong></td>
        <td><span class="badge ${active ? "active" : "suspended"}">${active ? "Active" : "Suspended"}</span></td>
        <td><span class="code">${escapeHtml(dateOnly(business.created_at))}</span></td>
        <td>
          <div class="row-actions">
            <button class="btn-sm btn-ok" onclick="viewBiz(${jsArg(business.business_id)}, ${jsArg(business.company_name)})" type="button">View</button>
            <button class="btn-sm" onclick="copyText(${jsArg(business.business_id)}, 'Business ID copied')" type="button">Copy ID</button>
            ${active
              ? `<button class="btn-sm btn-warn" onclick="suspendBiz(${jsArg(business.business_id)}, ${jsArg(business.company_name)})" type="button">Suspend</button>`
              : `<button class="btn-sm btn-ok" onclick="reinstateBiz(${jsArg(business.business_id)}, ${jsArg(business.company_name)})" type="button">Reinstate</button>`}
            <button class="btn-sm btn-danger" onclick="deleteBiz(${jsArg(business.business_id)}, ${jsArg(business.company_name)})" type="button">Delete</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function updateBusinessOptions() {
  const options = qs("#businessOptions");
  if (!options) return;
  options.innerHTML = state.businesses.map((business) => (
    `<option value="${escapeHtml(business.business_id)}">${escapeHtml(business.company_name || business.business_id)}</option>`
  )).join("");
}

function resetBusinessFilters() {
  qs("#bizSearch").value = "";
  qs("#bizStatusFilter").value = "all";
  renderBusinesses();
  updateUrlState();
}

async function viewBiz(bizId, name) {
  const detail = qs("#bizDetail");
  const tbody = qs("#bizDetailTable");
  qs("#bizDetailTitle").textContent = `${name || bizId} Team`;
  qs("#bizDetailMeta").textContent = bizId;
  detail.hidden = false;
  tbody.innerHTML = emptyRow("Loading...", 5);
  detail.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const data = await api(`/api/admino/business/${encodeURIComponent(bizId)}/team`);
    const team = data.team || [];
    if (!team.length) {
      tbody.innerHTML = emptyRow("No users in this business.", 5);
      return;
    }

    tbody.innerHTML = team.map((user) => `
      <tr>
        <td><span class="code">${escapeHtml(user.user_id)}</span></td>
        <td>${escapeHtml(user.username)}</td>
        <td><span class="badge ${user.role === "BusinessAdmin" ? "admino" : "active"}">${escapeHtml(user.role)}</span></td>
        <td><span class="badge active">Active</span></td>
        <td><span class="code">${escapeHtml(dateOnly(user.created_at))}</span></td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = emptyRow(err.message, 5);
    toast(err.message, "error");
  }
}

async function suspendBiz(bizId, name) {
  const result = await confirmAction({
    title: "Suspend business",
    message: `Suspend ${name || bizId}? Its users will be locked out until reinstated.`,
    okText: "Suspend",
    requireReason: true,
  });
  if (!result.confirmed) return;
  await mutateBusiness("/api/admino/suspend-business", bizId, "Business suspended", result.reason);
}

async function reinstateBiz(bizId, name) {
  const result = await confirmAction({
    title: "Reinstate business",
    message: `Reinstate ${name || bizId}? Users will be able to access it again.`,
    okText: "Reinstate",
    requireReason: true,
  });
  if (!result.confirmed) return;
  await mutateBusiness("/api/admino/reinstate-business", bizId, "Business reinstated", result.reason);
}

async function deleteBiz(bizId, name) {
  const result = await confirmAction({
    title: "Delete business",
    message: `Permanently delete ${name || bizId} and all of its users? This cannot be undone.`,
    confirmText: "DELETE",
    okText: "Delete",
    requireReason: true,
  });
  if (!result.confirmed) return;
  await mutateBusiness("/api/admino/delete-business", bizId, "Business deleted", result.reason);
}

async function mutateBusiness(url, businessId, successMessage, reason = "") {
  try {
    const data = await api(url, { method: "POST", body: JSON.stringify({ business_id: businessId, reason }) });
    toast(data.msg || successMessage);
    qs("#bizDetail").hidden = true;
    await Promise.all([loadBusinesses(), loadStats()]);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function adminoAddUser() {
  const btn = qs("#addUserBtn");
  btn.disabled = true;
  setAlert("injectAlert", "", "");
  try {
    const data = await api("/api/admino/add-user-to-business", {
      method: "POST",
      body: JSON.stringify({
        business_id: qs("#injectBizId").value.trim(),
        username: qs("#injectUser").value.trim(),
        password: qs("#injectPass").value,
        role: qs("#injectRole").value,
      }),
    });
    setAlert("injectAlert", data.msg || "User created", "success");
    toast("User created");
    qs("#injectUser").value = "";
    qs("#injectPass").value = "";
    if (state.activeView === "businesses") loadStats();
  } catch (err) {
    setAlert("injectAlert", err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function loadLogs() {
  const container = qs("#logsContainer");
  const biz = qs("#logBizFilter").value.trim();
  const action = qs("#logActionFilter").value.trim();
  const params = new URLSearchParams({ per_page: "50" });
  if (biz) params.set("business_id", biz);
  if (action) params.set("action", action);
  updateUrlState();

  container.innerHTML = '<div class="empty">Loading logs...</div>';
  try {
    const data = await api(`/api/admino/logs?${params.toString()}`);
    const logs = data.logs || [];
    state.logs = logs;
    qs("#logsMeta").textContent = `${logs.length} of ${data.total ?? logs.length} entries shown`;
    if (!logs.length) {
      container.innerHTML = emptyBlock("No logs found.", "Clear filters", "clearLogFilters()");
      return;
    }
    container.innerHTML = logs.map((log) => `
      <div class="log-entry">
        <div class="log-time">${escapeHtml(log.timestamp || "-")}</div>
        <div class="log-action">${escapeHtml(log.action || "-")}</div>
        <div>
          <span class="log-meta">actor:</span> ${escapeHtml(log.actor || "-")}
          ${log.business_id ? `<span class="log-meta"> biz:</span> <span class="code">${escapeHtml(log.business_id)}</span>` : ""}
          ${log.target ? `<span class="log-meta"> target:</span> ${escapeHtml(log.target)}` : ""}
          ${log.details && Object.keys(log.details).length ? `<span class="log-meta"> details:</span> <span class="code">${escapeHtml(JSON.stringify(log.details))}</span>` : ""}
        </div>
      </div>
    `).join("");
  } catch (err) {
    container.innerHTML = `<div class="empty">${escapeHtml(err.message)}</div>`;
    toast(err.message, "error");
  }
}

function clearLogFilters() {
  qs("#logBizFilter").value = "";
  qs("#logActionFilter").value = "";
  qs("#logsMeta").textContent = "Filter or load the latest activity.";
  qs("#logsContainer").innerHTML = '<div class="empty">Click Filter to load logs.</div>';
  state.logs = [];
  updateUrlState();
}

function csvCell(value) {
  return `"${String(value ?? "").replace(/"/g, '""')}"`;
}

function exportLogsCsv() {
  if (!state.logs.length) {
    toast("Load logs before exporting.", "error");
    return;
  }
  const rows = [
    ["timestamp", "action", "actor", "business_id", "target", "details"],
    ...state.logs.map((log) => [
      log.timestamp,
      log.action,
      log.actor,
      log.business_id,
      log.target,
      JSON.stringify(log.details || {}),
    ]),
  ];
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `admino-audit-logs-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  toast("Logs exported");
}

async function loadAdminos() {
  const tbody = qs("#adminoTable");
  tbody.innerHTML = emptyRow("Loading...");
  try {
    const data = await api("/api/admino/adminos");
    state.adminos = data.adminos || [];
    renderAdminos();
  } catch (err) {
    tbody.innerHTML = emptyRow(err.message);
    toast(err.message, "error");
  }
}

function renderAdminos() {
  const query = qs("#adminoSearch").value.trim().toLowerCase();
  const me = state.user || decodeToken() || {};
  const list = state.adminos.filter((admino) => {
    const haystack = `${admino.user_id || ""} ${admino.username || ""}`.toLowerCase();
    return !query || haystack.includes(query);
  });
  qs("#adminoCount").textContent = `${list.length} of ${state.adminos.length} adminos shown`;

  if (!list.length) {
    qs("#adminoTable").innerHTML = `<tr><td colspan="5">${emptyBlock("No adminos match the current search.", "Reset search", "resetAdminoSearch()")}</td></tr>`;
    return;
  }

  qs("#adminoTable").innerHTML = list.map((admino) => {
    const isMe = admino.user_id === me.user_id;
    const active = admino.active !== false;
    return `
      <tr>
        <td><span class="code">${escapeHtml(admino.user_id)}</span></td>
        <td><strong>${escapeHtml(admino.username)}</strong> ${isMe ? '<span class="badge admino">you</span>' : ""}</td>
        <td><span class="badge ${active ? "active" : "inactive"}">${active ? "Active" : "Inactive"}</span></td>
        <td><span class="code">${escapeHtml(dateOnly(admino.created_at))}</span></td>
        <td>
          ${isMe ? '<span class="code">-</span>' : `
            <div class="row-actions">
              <button class="btn-sm btn-warn" onclick="deactivateAdmino(${jsArg(admino.user_id)}, ${jsArg(admino.username)})" type="button">Deactivate</button>
              <button class="btn-sm btn-danger" onclick="deleteAdmino(${jsArg(admino.user_id)}, ${jsArg(admino.username)})" type="button">Delete</button>
            </div>
          `}
        </td>
      </tr>
    `;
  }).join("");
}

function resetAdminoSearch() {
  qs("#adminoSearch").value = "";
  renderAdminos();
  updateUrlState();
}

async function createAdmino() {
  const btn = qs("#createAdminoBtn");
  btn.disabled = true;
  setAlert("adminoAlert", "", "");
  try {
    const data = await api("/api/admino/create-admino", {
      method: "POST",
      body: JSON.stringify({
        username: qs("#newAdminoUser").value.trim(),
        password: qs("#newAdminoPass").value,
      }),
    });
    setAlert("adminoAlert", data.msg || "Admino created", "success");
    toast("Admino created");
    qs("#newAdminoUser").value = "";
    qs("#newAdminoPass").value = "";
    await Promise.all([loadAdminos(), loadStats()]);
  } catch (err) {
    setAlert("adminoAlert", err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function deactivateAdmino(userId, username) {
  const result = await confirmAction({
    title: "Deactivate admino",
    message: `Deactivate ${username || userId}? They will lose platform access.`,
    okText: "Deactivate",
    requireReason: true,
  });
  if (!result.confirmed) return;

  try {
    const data = await api("/api/admino/deactivate-admino", { method: "POST", body: JSON.stringify({ user_id: userId, reason: result.reason }) });
    toast(data.msg || "Admino deactivated");
    await Promise.all([loadAdminos(), loadStats()]);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function deleteAdmino(userId, username) {
  const result = await confirmAction({
    title: "Delete admino",
    message: `Permanently delete admino ${username || userId}? This cannot be undone.`,
    confirmText: "DELETE",
    okText: "Delete",
    requireReason: true,
  });
  if (!result.confirmed) return;

  try {
    const data = await api("/api/admino/delete-admino", { method: "POST", body: JSON.stringify({ user_id: userId, reason: result.reason }) });
    toast(data.msg || "Admino deleted");
    await Promise.all([loadAdminos(), loadStats()]);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    toast(message || "Copied");
  } catch (err) {
    toast("Unable to copy from this browser context.", "error");
  }
}

function generatedPassword() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%";
  const required = ["A", "a", "7", "!"];
  while (required.length < 16) {
    required.push(chars[Math.floor(Math.random() * chars.length)]);
  }
  return required.sort(() => Math.random() - 0.5).join("");
}

async function fillGeneratedPassword(inputId) {
  const input = qs(`#${inputId}`);
  input.value = generatedPassword();
  input.type = "text";
  await copyText(input.value, "Password generated and copied");
}

function togglePassword(inputId, button) {
  const input = qs(`#${inputId}`);
  const hidden = input.type === "password";
  input.type = hidden ? "text" : "password";
  button.textContent = hidden ? "Hide" : "Show";
}

function focusPrimarySearch() {
  const target = state.activeView === "adminos"
    ? qs("#adminoSearch")
    : state.activeView === "logs"
      ? qs("#logBizFilter")
      : qs("#bizSearch");
  if (target) target.focus();
}

function bindKeyboardShortcuts() {
  document.addEventListener("keydown", (event) => {
    const tag = event.target.tagName;
    const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    if (event.key === "Escape") {
      if (!qs("#confirmModal").hidden) qs("#confirmCancel").click();
      qs("#bizDetail").hidden = true;
      return;
    }
    if (typing) return;
    if (event.key === "/") {
      event.preventDefault();
      focusPrimarySearch();
    }
    if (event.key.toLowerCase() === "r") {
      refreshActiveView();
    }
  });
}

function bindEvents() {
  qsa("[data-view]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });
  qsa("[data-view-jump]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.viewJump));
  });
  qsa("[data-biz-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.bizSort;
      state.bizSort = {
        key,
        dir: state.bizSort.key === key && state.bizSort.dir === "asc" ? "desc" : "asc",
      };
      renderBusinesses();
    });
  });

  qs("#logoutBtn").addEventListener("click", logout);
  qs("#refreshBtn").addEventListener("click", refreshActiveView);
  qs("#bizSearch").addEventListener("input", () => { renderBusinesses(); updateUrlState(); });
  qs("#bizStatusFilter").addEventListener("change", () => { renderBusinesses(); updateUrlState(); });
  qs("#adminoSearch").addEventListener("input", () => { renderAdminos(); updateUrlState(); });
  qs("#loadLogsBtn").addEventListener("click", loadLogs);
  qs("#exportLogsBtn").addEventListener("click", exportLogsCsv);
  qs("#clearLogsBtn").addEventListener("click", clearLogFilters);
  qs("#addUserBtn").addEventListener("click", adminoAddUser);
  qs("#createAdminoBtn").addEventListener("click", createAdmino);
  qs("#closeBizDetail").addEventListener("click", () => { qs("#bizDetail").hidden = true; });
  qsa("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => togglePassword(button.dataset.togglePassword, button));
  });
  qsa("[data-generate-password]").forEach((button) => {
    button.addEventListener("click", () => fillGeneratedPassword(button.dataset.generatePassword));
  });
  bindKeyboardShortcuts();
}

async function init() {
  await loadCsrfToken();
  bindEvents();
  const user = decodeToken();
  if (!user) {
    window.location.href = "/";
    return;
  }
  if (user.exp * 1000 < Date.now() || user.role !== "admino") {
    localStorage.removeItem("token");
    window.location.href = user.role !== "admino" ? "/dashboard" : "/";
    return;
  }

  state.user = user;
  qs("#sidebarUser").textContent = user.username || "-";
  qs("#avatarInitial").textContent = (user.username || "?").charAt(0).toUpperCase();
  const initialView = restoreUrlState();
  showView(titles[initialView] ? initialView : "overview");
}

window.showView = showView;
window.viewBiz = viewBiz;
window.suspendBiz = suspendBiz;
window.reinstateBiz = reinstateBiz;
window.deleteBiz = deleteBiz;
window.deactivateAdmino = deactivateAdmino;
window.deleteAdmino = deleteAdmino;
window.copyText = copyText;
window.resetBusinessFilters = resetBusinessFilters;
window.resetAdminoSearch = resetAdminoSearch;
window.clearLogFilters = clearLogFilters;

init();
