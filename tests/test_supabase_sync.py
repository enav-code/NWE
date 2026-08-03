import unittest
from unittest.mock import patch

import Storage


class SupabaseSyncTests(unittest.TestCase):
    def test_sync_all_users_posts_each_user_to_supabase(self):
        store = {
            "businesses": {
                "biz_1": {
                    "business_id": "biz_1",
                    "company_name": "Acme",
                    "users": {
                        "user_1": {
                            "user_id": "user_1",
                            "username": "owner@example.com",
                            "role": "BusinessAdmin",
                            "active": True,
                            "created_at": "2024-01-01T00:00:00Z",
                        }
                    },
                }
            },
            "adminos": {
                "user_2": {
                    "user_id": "user_2",
                    "username": "admino@example.com",
                    "role": "admino",
                    "active": True,
                    "created_at": "2024-01-02T00:00:00Z",
                }
            },
        }

        with patch("Storage.load_store", return_value=store), patch("Storage._post_profile_to_supabase") as mock_post:
            Storage.sync_all_users_to_supabase()

        self.assertEqual(mock_post.call_count, 2)
        first_payload = mock_post.call_args_list[0].args[0]
        self.assertEqual(first_payload["id"], "user_1")
        self.assertEqual(first_payload["username"], "owner@example.com")
        self.assertEqual(first_payload["business_id"], "biz_1")


if __name__ == "__main__":
    unittest.main()
