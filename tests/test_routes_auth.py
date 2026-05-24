import uuid
import unittest

from dotenv import load_dotenv


class AuthRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        try:
            from run import app
            from src.utils.database_helper import db, client
        except ImportError as exc:
            raise unittest.SkipTest(f"Dependencies unavailable: {exc}") from exc

        cls.client = app.test_client()
        cls.mongo_client = client
        cls.businesses = db["businesses"]
        cls.users = db["users"]

    @classmethod
    def tearDownClass(cls):
        pass  # MongoDB client is managed by conftest.py

    def setUp(self):
        self.created_business_emails = []
        self.created_user_emails = []

    def tearDown(self):
        if self.created_business_emails:
            self.businesses.delete_many({"email": {"$in": self.created_business_emails}})
        if self.created_user_emails:
            self.users.delete_many({"email": {"$in": self.created_user_emails}})

    def _unique_email(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex}@example.com"

    def test_business_auth_flow(self):
        email = self._unique_email("biz")
        self.created_business_emails.append(email)

        register_payload = {
            "name": "Test Business",
            "email": email,
            "password": "Password123!",
        }
        register_response = self.client.post(
            "/api/v1/business/auth/register",
            json=register_payload,
        )
        self.assertEqual(register_response.status_code, 201)
        register_data = register_response.get_json()
        self.assertIn("access_token", register_data)
        self.assertIn("refresh_token", register_data)

        login_response = self.client.post(
            "/api/v1/business/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        self.assertEqual(login_response.status_code, 200)
        login_data = login_response.get_json()
        access_token = login_data["access_token"]
        refresh_token = login_data["refresh_token"]

        refresh_response = self.client.post(
            "/api/v1/business/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        self.assertEqual(refresh_response.status_code, 200)
        refresh_data = refresh_response.get_json()
        self.assertIn("access_token", refresh_data)

        edit_response = self.client.put(
            "/api/v1/business/auth/edit",
            json={"name": "Updated Business"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(edit_response.status_code, 200)
        edit_data = edit_response.get_json()
        self.assertEqual(edit_data["business"]["name"], "Updated Business")

        delete_response = self.client.delete(
            "/api/v1/business/auth/delete",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(delete_response.status_code, 200)

    def test_client_auth_flow(self):
        email = self._unique_email("client")
        self.created_user_emails.append(email)

        register_payload = {
            "first_name": "Test",
            "last_name": "Client",
            "phone_number": "1234567890",
            "email": email,
            "password": "Password123!",
        }
        register_response = self.client.post(
            "/api/v1/client/auth/register",
            json=register_payload,
        )
        self.assertEqual(register_response.status_code, 201)
        register_data = register_response.get_json()
        self.assertIn("access_token", register_data)
        self.assertIn("refresh_token", register_data)

        login_response = self.client.post(
            "/api/v1/client/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        self.assertEqual(login_response.status_code, 200)
        login_data = login_response.get_json()
        access_token = login_data["access_token"]
        refresh_token = login_data["refresh_token"]

        refresh_response = self.client.post(
            "/api/v1/client/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        self.assertEqual(refresh_response.status_code, 200)
        refresh_data = refresh_response.get_json()
        self.assertIn("access_token", refresh_data)

        edit_response = self.client.put(
            "/api/v1/client/auth/edit",
            json={"first_name": "Updated"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(edit_response.status_code, 200)
        edit_data = edit_response.get_json()
        self.assertEqual(edit_data["user"]["first_name"], "Updated")

        delete_response = self.client.delete(
            "/api/v1/client/auth/delete",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(delete_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()

