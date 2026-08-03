import json
import os
import tempfile
import unittest

import App


class IpBanTests(unittest.TestCase):
    def test_banned_ip_is_blocked(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            json.dump(["203.0.113.5"], handle)
            temp_path = handle.name

        original_ban_file = App.BAN_FILE
        App.BAN_FILE = temp_path
        try:
            client = App.app.test_client()
            response = client.get("/", environ_overrides={"REMOTE_ADDR": "203.0.113.5"})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json()["msg"], "ip blocked")
        finally:
            App.BAN_FILE = original_ban_file
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
