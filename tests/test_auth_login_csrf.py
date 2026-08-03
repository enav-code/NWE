import unittest
from unittest.mock import patch

import App


class AuthLoginCsrfTests(unittest.TestCase):
    def test_login_post_is_not_blocked_by_csrf(self):
        client = App.app.test_client()
        with patch("routes.auth.sign_in_with_supabase", return_value=None), patch("routes.auth.find_user_by_username", return_value=(None, None, None)):
            response = client.post(
                "/api/auth/login",
                json={"username": "friend@example.com", "password": "secret123"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["msg"], "invalid credentials")


if __name__ == "__main__":
    unittest.main()
