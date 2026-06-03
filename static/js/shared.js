let currentUser = null;
let csrfToken = "";
let currentPermissions = {};
let logPage = 1;
let logPerPage = 20;
let logTotal = 0;

const roleLabels = {
    "admin": "Admin",
    "operator": "Operator",
    "moderator": "Moderator",
    "support": "Support",
    "readonly_admin": "Readonly Admin",
    "viewer": "Viewer",
};


function escapeHtml(text) {
    if (!text) return "";
    const map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}


function jsString(text) {
    return JSON.stringify(String(text || ""));
}


function showToast(message, type = "success") {
    let area = document.getElementById("toastArea");
    if (!area) {
        area = document.createElement("div");
        area.id = "toastArea";
        area.className = "toast-area";
        document.body.appendChild(area);
    }
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;
    area.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}


async function loadCSRF() {

    const res = await fetch("/api/auth/csrf", {
        credentials: "include"
    });

    const data = await res.json();

    csrfToken = data.csrf_token;
}


function csrfHeaders() {
    return {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
    };
}


async function api(url, options = {}) {

    options.credentials = "include";

    options.headers = {
        ...(options.headers || {}),
        "X-CSRF-Token": csrfToken
    };

    return fetch(url, options);
}


async function loadMe() {

    const res = await api("/api/auth/me");

    if (!res.ok) {
        console.error("Failed to load user info, status:", res.status);
        window.location.href = "/";
        return;
    }

    const data = await res.json();
    console.log("User data loaded:", data);

    currentUser = data;
    currentPermissions = data.permissions ? data.permissions.reduce((acc, perm) => { acc[perm] = true; return acc; }, {}) : {};

    const userInfo = document.getElementById("userInfo");

    if (userInfo) {
        userInfo.innerText =
            `LOGGED IN AS: ${data.username} (${data.role})`;
    }

    const adminButton =
        document.getElementById("adminButton");

    if (adminButton) {

        if (data.role === "admin") {
            adminButton.removeAttribute("hidden");
            console.log("Admin button unhidden for admin user");
        } else {
            adminButton.setAttribute("hidden", "");
        }
    }

    const operationsButton =
        document.getElementById("operationsButton");

    if (operationsButton) {

        if (data.role === "admin") {
            operationsButton.removeAttribute("hidden");
            console.log("Operations button unhidden for admin user");
        } else {
            operationsButton.setAttribute("hidden", "");
        }
    }
}


async function logout() {

    await api("/api/auth/logout", {
        method: "POST"
    });

    window.location.href = "/";
}


async function loadPermissions() {
    const res = await fetch("/api/admin/permissions", { credentials: "include" });
    if (!res.ok) return null;
    return res.json();
}


async function loadSessions() {
    if (!document.getElementById("sessions")) return;
    const res = await fetch("/api/admin/sessions", { credentials: "include" });
    if (!res.ok) {
        document.getElementById("sessions").innerText = "Unable to load sessions.";
        return;
    }
    const data = await res.json();
    const sessions = data.sessions || [];
    document.getElementById("sessions").innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>User</th>
                    <th>Role</th>
                    <th>Last Seen</th>
                    <th>Expires</th>
                    <th>Remember</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${sessions.map(item => `
                    <tr>
                        <td>${escapeHtml(item.username)}${item.current ? " (current)" : ""}</td>
                        <td>${escapeHtml(roleLabels[item.role] || item.role)}</td>
                        <td>${escapeHtml(item.last_seen)}</td>
                        <td>${escapeHtml(item.expires_at)}</td>
                        <td>${item.remember ? "Yes" : ""}</td>
                        <td><button onclick='forceLogoutUser(${jsString(item.username)})'>Logout User</button></td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
}


function goAdmin() {
    window.location.href = "/admin";
}


function goOperations() {
    window.location.href = "/operations";
}


function goBack() {
    window.history.back();
}