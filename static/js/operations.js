async function initOperations() {
    await loadMe();
    await refreshOperations();
}

async function refreshOperations() {
    await Promise.all([loadStats(), loadLogs(), loadSessions(), loadBackups()]);
}

async function forceLogoutAll() {
    const res = await fetch("/api/admin/force-logout", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ include_current: false, exclude_admin: true }),
    });
    const data = await res.json();
    showToast(data.msg || "Done");
    await Promise.all([loadSessions(), loadLogs()]);
}

async function forceLogoutUser(username) {
    const res = await fetch("/api/admin/force-logout", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ username, include_current: username === currentUser?.username }),
    });
    const data = await res.json();
    showToast(data.msg || "Done");
    if (username === currentUser?.username) {
        window.location.href = "/";
        return;
    }
    await Promise.all([loadSessions(), loadLogs()]);
}

async function loadBackups() {
    if (!document.getElementById("backups")) return;
    const res = await fetch("/api/admin/backups", { credentials: "include" });
    if (!res.ok) {
        document.getElementById("backups").innerText = "Unable to load backups.";
        return;
    }
    const data = await res.json();
    const backups = data.backups || [];
    document.getElementById("backups").innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Created</th>
                </tr>
            </thead>
            <tbody>
                ${backups.map(item => `
                    <tr>
                        <td>${escapeHtml(item.name)}</td>
                        <td>${escapeHtml(item.created_at)}</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
}

async function restoreBackup(target) {
    const res = await fetch("/api/admin/restore-backup", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ target }),
    });
    const data = await res.json();
    showToast(data.msg || "Done", res.ok ? "success" : "error");
    await refreshOperations();
}