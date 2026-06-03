#!/usr/bin/env python3
"""Test to see where sessions are being cleared."""

import os
os.environ["SECRET_KEY"] = "test-key"

from App import app

# Disable CSRF for testing
app.config["WTF_CSRF_ENABLED"] = False

client = app.test_client()

print("\n" + "="*70)
print("TEST: LOGIN THEN CALL /me")
print("="*70 + "\n")

print("[1] Logging in...")
login = client.post("/api/auth/login", json={
    "username": "testadmin",
    "password": "TestPass123!"
})
print(f"    Status: {login.status_code}")

print("\n[2] Immediately calling /me endpoint...")
me = client.get("/api/auth/me")
print(f"    Status: {me.status_code}")

if me.status_code == 200:
    print(f"    [OK] SUCCESS")
else:
    print(f"    [ERROR] {me.get_json()}")
