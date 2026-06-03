#!/usr/bin/env python3
"""
Application startup script with proper environment setup.
Run this instead of: python App.py
"""

import os
import sys

# 1. Ensure SECRET_KEY is set
if not os.environ.get("SECRET_KEY"):
    print("=" * 70)
    print("SETTING UP APPLICATION")
    print("=" * 70)
    
    # Generate a stable secret key
    import secrets
    secret = secrets.token_hex(32)
    os.environ["SECRET_KEY"] = secret
    
    print(f"\n[OK] SECRET_KEY generated: {secret}")
    print("\nIMPORTANT: To persist this SECRET_KEY across restarts:")
    print("  Windows (PowerShell):")
    print(f"    $env:SECRET_KEY = '{secret}'")
    print("  Linux/Mac (Bash):")
    print(f"    export SECRET_KEY={secret}")
    print("\n" + "=" * 70 + "\n")

# 2. Start the Flask app
from App import app

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_ENV") != "production"
    force_https = os.environ.get("FORCE_HTTPS", "0").lower() in ("1", "true", "yes")
    use_https = True if force_https else os.environ.get("USE_HTTPS", "").lower() in ("1", "true", "yes")
    
    print(f"Starting Flask app...")
    print(f"  DEBUG: {debug_mode}")
    print(f"  HTTPS: {use_https}")
    print(f"  SECRET_KEY: {'SET' if os.environ.get('SECRET_KEY') else 'NOT SET'}")
    print(f"  URL: {'https' if use_https else 'http'}://localhost:{'3000' if use_https else '5000'}")
    print()
    
    if use_https:
        try:
            import cryptography  # noqa: F401
            ssl_context = "adhoc"
        except ImportError:
            print("ERROR: HTTPS requires cryptography: pip install cryptography")
            sys.exit(1)
        app.run(host="127.0.0.1", port=3000, debug=debug_mode, ssl_context=ssl_context)
    else:
        app.run(host="127.0.0.1", port=5000, debug=debug_mode)
