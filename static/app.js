let csrfToken = "";

const userInfo = document.getElementById("userInfo");


async function loadCSRF() {

    const res = await fetch("/csrf-token", {
        credentials: "include"
    });

    const data = await res.json();

    csrfToken = data.csrf_token;

    console.log("CSRF LOADED");
}


async function api(url, options = {}) {

    options.credentials = "include";

    options.headers = {
        ...(options.headers || {}),
        "X-CSRF-Token": csrfToken
    };

    return fetch(url, options);
}


async function login() {

    const username =
        document.getElementById("username").value;

    const password =
        document.getElementById("password").value;

    const res = await api("/api/auth/login", {

        method: "POST",

        headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken
        },

        body: JSON.stringify({
            username,
            password
        })
    });

    const data = await res.json();

    if (data.msg === "ok") {
        window.location.href = "/dashboard";
        return;
    }

    alert(data.msg || "LOGIN FAILED");
}


async function register() {

    const username =
        document.getElementById("username").value;

    const password =
        document.getElementById("password").value;

    const res = await api("/api/auth/register", {

        method: "POST",

        headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken
        },

        body: JSON.stringify({
            username,
            password
        })
    });

    const data = await res.json();

    alert(data.msg);
}


async function logout() {

    await api("/api/auth/logout", {
        method: "POST"
    });

    window.location.href = "/";
}


async function loadMe() {

    const res = await fetch("/api/auth/me", {
        credentials: "include"
    });

    if (!res.ok) {

        window.location.href = "/";
        return;
    }

    const data = await res.json();

    if (userInfo) {
        userInfo.innerText =
            `${data.username} (${data.role})`;
    }
}


window.onload = async () => {

    await loadCSRF();

    if (
        window.location.pathname === "/dashboard"
    ) {
        await loadMe();
    }
};