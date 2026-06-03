let allUsers = [];
let selected = new Set();
let userPage = 1;
let userPerPage = 10;
let userTotal = 0;

async function initAdmin() {
    await loadMe();
    await loadUsers();
}

async function loadUsers() {
    const res = await fetch(`/api/admin/users?page=${userPage}&per_page=${userPerPage}`, { credentials: "include" });
    if (!res.ok) {
        document.getElementById("users").innerHTML = "ACCESS DENIED";
        return;
    }
    const data = await res.json();
    selected.clear();
    allUsers = data.users || [];
    userTotal = data.total || allUsers.length;
    render(allUsers);
    document.getElementById("usersPageInfo").innerText = `Page ${data.page} / ${Math.max(1, Math.ceil(userTotal / userPerPage))}`;
}

function render(list) {
    document.getElementById("users").innerHTML = list.map(u => {
        const username = escapeHtml(u.username);
        return `
            <div class="user-card">
                <label class="user-select">
                    <input type="checkbox" onchange="toggleSelect('${username}')" ${selected.has(u.username) ? "checked" : ""}>
                    <span>${username}</span>
                </label>
                <div class="tag">${escapeHtml(roleLabels[u.role] || u.role)} ${u.active === false ? "(disabled)" : ""}</div>
                <div class="user-actions">
                    ${currentPermissions.change_role ? `
                        <button onclick="setRole('${username}','admin')">Admin</button>
                        <button onclick="setRole('${username}','operator')">Operator</button>
                        <button onclick="setRole('${username}','viewer')">Viewer</button>
                    ` : ""}
                    ${currentPermissions.edit_user ? `<button onclick="editUserPrompt('${username}')">Edit</button>` : ""}
                    ${currentPermissions.delete_user ? `<button onclick="deleteUser('${username}')">Delete</button>` : ""}
                </div>
            </div>
        `;
    }).join("");
}

function filterUsers() {
    const q = document.getElementById("search").value.toLowerCase();
    render(allUsers.filter(u => u.username.toLowerCase().includes(q)));
}

async function createUser() {
    const usernameValue = document.getElementById("newUsername").value.trim();
    const passwordValue = document.getElementById("newPassword").value;
    const roleValue = document.getElementById("newRole").value;
    const msg = document.getElementById("createMsg");

    if (!usernameValue || !passwordValue) {
        msg.innerText = "Username and password are required.";
        return;
    }

    const res = await fetch("/api/admin/create-user", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ username: usernameValue, password: passwordValue, role: roleValue }),
    });

    const data = await res.json();
    if (res.ok) {
        msg.innerText = "User created.";
        showToast("User created.");
        document.getElementById("newUsername").value = "";
        document.getElementById("newPassword").value = "";
        await Promise.all([loadUsers(), loadStats(), loadLogs()]);
    } else {
        msg.innerText = data.msg || "Failed to create user.";
        showToast(msg.innerText, "error");
    }
}

async function setRole(username, role) {
    const res = await fetch("/api/admin/set-role", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ username, role }),
    });
    const data = await res.json();
    if (!res.ok) {
        showToast(data.msg || "Unable to update role", "error");
        return;
    }
    await Promise.all([loadUsers(), loadStats(), loadLogs()]);
    showToast("Role updated.");
}

async function deleteUser(username) {
    const res = await fetch("/api/admin/delete-user", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ username }),
    });
    const data = await res.json();
    if (!res.ok) {
        showToast(data.msg || "Unable to delete user", "error");
        return;
    }
    await Promise.all([loadUsers(), loadStats(), loadLogs(), loadSessions()]);
    showToast("User deleted.");
}

async function bulkDelete() {
    if (selected.size === 0) {
        alert("Select users to delete.");
        return;
    }
    const usernames = Array.from(selected);
    const res = await fetch("/api/admin/delete-users", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ usernames }),
    });
    const data = await res.json();
    if (!res.ok) {
        showToast(data.msg || "Failed to delete users", "error");
        return;
    }
    selected.clear();
    await Promise.all([loadUsers(), loadStats(), loadLogs()]);
    showToast(`Removed ${data.removed} user(s).`);
}

function toggleSelect(user) {
    if (selected.has(user)) selected.delete(user);
    else selected.add(user);
}

function usersNext() {
    const max = Math.max(1, Math.ceil(userTotal / userPerPage));
    if (userPage < max) {
        userPage += 1;
        loadUsers();
    }
}

function usersPrev() {
    if (userPage > 1) {
        userPage -= 1;
        loadUsers();
    }
}

async function loadStats() {
    const res = await fetch("/api/admin/stats", { credentials: "include" });
    if (!res.ok) {
        document.getElementById("stats").innerText = "Unable to load stats.";
        return;
    }
    const data = await res.json();
    document.getElementById("stats").innerText = `Total: ${data.total} | Admins: ${data.admins} | Users: ${data.viewers}`;
}

async function loadLogs() {
    if (!document.getElementById("logs")) return;
    const res = await fetch(`/api/admin/logs?page=${logPage}&per_page=${logPerPage}`, { credentials: "include" });
    if (!res.ok) {
        document.getElementById("logs").innerText = "Unable to load logs.";
        return;
    }
    const data = await res.json();
    const logs = data.logs || [];
    logTotal = data.total || logs.length;
    document.getElementById("logs").innerHTML = logs.map(l => `
        <div class="log-entry">
            <div><strong>${escapeHtml(l.timestamp)}</strong> - ${escapeHtml(l.action)}</div>
            <div>${escapeHtml(l.actor || "system")} -> ${escapeHtml(l.target)}</div>
            <div>${escapeHtml(JSON.stringify(l.details))}</div>
        </div>
    `).join("");
    document.getElementById("logsPageInfo").innerText = `Page ${data.page} / ${Math.max(1, Math.ceil(logTotal / logPerPage))}`;
}

function logsNext() {
    const max = Math.max(1, Math.ceil(logTotal / logPerPage));
    if (logPage < max) {
        logPage += 1;
        loadLogs();
    }
}

function logsPrev() {
    if (logPage > 1) {
        logPage -= 1;
        loadLogs();
    }
}

async function editUserPrompt(username) {
    const user = allUsers.find(u => u.username === username);
    if (!user) return alert("user not found");

    const newRole = currentPermissions.change_role
        ? (prompt("Role (admin/operator/moderator/support/readonly_admin/viewer):", user.role) || user.role)
        : user.role;
    const newPassword = prompt("New password (leave blank to keep):", "");
    const active = confirm("Press OK to mark account ACTIVE; Cancel to mark DISABLED");

    const payload = { username, role: newRole, active };
    if (newPassword) payload.password = newPassword;

    const res = await fetch("/api/admin/edit-user", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(payload),
    });

    if (!res.ok) {
        const d = await res.json();
        return showToast(d.msg || "Failed to update user", "error");
    }

    await Promise.all([loadUsers(), loadStats(), loadLogs(), loadSessions()]);
    showToast("User updated.");
}