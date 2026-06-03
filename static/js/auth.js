async function login() {
    const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        credentials: "include",
        body: JSON.stringify({
            username: username.value,
            password: password.value,
            remember: document.getElementById("rememberMe")?.checked || false,
        }),
    });
    const data = await res.json();
    if (res.ok) {
        window.location.href = "/dashboard";
    } else {
        msg.innerText = data.msg;
    }
}

async function register() {
    const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        credentials: "include",
        body: JSON.stringify({
            username: username.value,
            password: password.value,
        }),
    });
    const data = await res.json();
    msg.innerText = res.ok ? "created" : (data.msg || "error");
}
