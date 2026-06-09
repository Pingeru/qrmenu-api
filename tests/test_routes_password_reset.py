import copy
import os
import unittest
import uuid
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from bson import ObjectId
from dotenv import load_dotenv

import tests.conftest as pytest_conftest

pytest_conftest._mongo_client = object()
pytest_conftest._db = object()

from src.utils import auth_helper
from src.utils.password_reset_helper import (
    create_password_reset_token,
    decode_password_reset_token,
    send_password_reset_email,
)
from src.utils.auth_helper import verify_password


class FakeUpdateResult:
    def __init__(self, matched_count: int):
        self.matched_count = matched_count


class FakeCollection:
    def __init__(self, docs: list[dict]):
        self.docs = [copy.deepcopy(doc) for doc in docs]

    def _matches(self, doc: dict, query: dict) -> bool:
        for key, expected in query.items():
            actual = doc.get(key)
            if key == "_id":
                if str(actual) != str(expected):
                    return False
            elif actual != expected:
                return False
        return True

    def find_one(self, query: dict):
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    def update_one(self, query: dict, update: dict):
        doc = self.find_one(query)
        if not doc:
            return FakeUpdateResult(0)

        if "$set" in update:
            doc.update(update["$set"])
        return FakeUpdateResult(1)


class PasswordResetRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        os.environ["JWT_SECRET"] = "c" * 128
        os.environ["JWT_REFRESH_SECRET"] = "c" * 128
        os.environ["ACCESS_TOKEN_TTL_MIN"] = "5"
        os.environ["REFRESH_TOKEN_TTL_DAYS"] = "5"
        os.environ["PASSWORD_RESET_TOKEN_TTL_MIN"] = "10"
        os.environ["APP_NAME"] = "QR Menu"

        try:
            from run import app
            import src.routes.business_auth as business_auth_module
            import src.routes.client_auth as client_auth_module
            import src.routes.password_reset as password_reset_module
        except ImportError as exc:
            raise unittest.SkipTest(f"Dependencies unavailable: {exc}") from exc

        app.testing = True
        cls.app = app
        cls.client = app.test_client()
        cls.business_auth_module = business_auth_module
        cls.client_auth_module = client_auth_module
        cls.password_reset_module = password_reset_module

    def setUp(self):
        self.business_doc = None
        self.client_doc = None
        self.business_collection = FakeCollection([])
        self.client_collection = FakeCollection([])
        self.business_auth_module.businesses = self.business_collection
        self.client_auth_module.users = self.client_collection
        self.password_reset_module.businesses = self.business_collection
        self.password_reset_module.users = self.client_collection

    def _install_account(self, account_type: str, doc: dict):
        if account_type == "business":
            self.business_collection = FakeCollection([doc])
            self.business_auth_module.businesses = self.business_collection
            self.password_reset_module.businesses = self.business_collection
            self.business_doc = doc
        else:
            self.client_collection = FakeCollection([doc])
            self.client_auth_module.users = self.client_collection
            self.password_reset_module.users = self.client_collection
            self.client_doc = doc

    def test_password_reset_email_uses_forwarded_origin_and_template(self):
        account_doc = {
            "_id": ObjectId(),
            "email": "owner@example.com",
            "name": "Coffee House",
        }
        captured = {}

        with patch(
            "src.utils.password_reset_helper._deliver_password_reset_email",
            side_effect=lambda **kwargs: captured.update(kwargs),
        ):
            with self.app.test_request_context(
                "/",
                headers={
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-Host": "example.com",
                },
            ):
                reset_url = send_password_reset_email(account_doc, "business")

        self.assertTrue(reset_url.startswith("https://example.com/password-reset?token="))
        self.assertEqual(captured["recipient_email"], "owner@example.com")
        self.assertEqual(captured["reset_url"], reset_url)
        self.assertIn("reset password", captured["html_body"])
        self.assertIn(reset_url, captured["html_body"])

        token = parse_qs(urlparse(reset_url).query)["token"][0]
        payload = decode_password_reset_token(token)
        self.assertEqual(payload["sub"], str(account_doc["_id"]))
        self.assertEqual(payload["user_type"], "password_reset_business")
        self.assertEqual(payload["purpose"], "password_reset")
        self.assertEqual(payload["account_type"], "business")

    def test_business_forgot_password_endpoint(self):
        email = f"biz-{uuid.uuid4().hex}@example.com"
        account_doc = {
            "_id": ObjectId(),
            "name": "Test Business",
            "email": email,
            "password_hash": auth_helper.hash_password("Password123!"),
        }
        self._install_account("business", account_doc)
        captured = {}

        with patch(
            "src.routes.business_auth.send_password_reset_email",
            side_effect=lambda account_doc, account_type: captured.update(
                {"account_doc": account_doc, "account_type": account_type}
            ),
        ):
            response = self.client.post("/api/v1/business/auth/forgot-password", json={"email": email})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"message": "If the account exists, a password reset email has been sent"},
        )
        self.assertEqual(captured["account_type"], "business")
        self.assertEqual(captured["account_doc"]["email"], email)

    def test_business_forgot_password_requires_email(self):
        response = self.client.post("/api/v1/business/auth/forgot-password", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "Missing required fields"})

    def test_client_forgot_password_endpoint(self):
        email = f"client-{uuid.uuid4().hex}@example.com"
        account_doc = {
            "_id": ObjectId(),
            "first_name": "Test",
            "last_name": "Client",
            "email": email,
            "password_hash": auth_helper.hash_password("Password123!"),
        }
        self._install_account("client", account_doc)
        captured = {}

        with patch(
            "src.routes.client_auth.send_password_reset_email",
            side_effect=lambda account_doc, account_type: captured.update(
                {"account_doc": account_doc, "account_type": account_type}
            ),
        ):
            response = self.client.post("/api/v1/client/auth/forgot-password", json={"email": email})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"message": "If the account exists, a password reset email has been sent"},
        )
        self.assertEqual(captured["account_type"], "client")
        self.assertEqual(captured["account_doc"]["email"], email)

    def test_password_reset_page_requires_token(self):
        response = self.client.get("/password-reset")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing reset token", response.get_data(as_text=True))

    def test_password_reset_page_updates_password_for_business_and_client(self):
        scenarios = [
            (
                "business",
                {
                    "_id": ObjectId(),
                    "name": "Coffee House",
                    "email": "business@example.com",
                    "password_hash": auth_helper.hash_password("OldPassword123!"),
                },
            ),
            (
                "client",
                {
                    "_id": ObjectId(),
                    "first_name": "Ali",
                    "last_name": "Veli",
                    "email": "client@example.com",
                    "password_hash": auth_helper.hash_password("OldPassword123!"),
                },
            ),
        ]

        for account_type, account_doc in scenarios:
            with self.subTest(account_type=account_type):
                self._install_account(account_type, account_doc)
                token = create_password_reset_token(str(account_doc["_id"]), account_type)
                target_collection = self.business_collection if account_type == "business" else self.client_collection

                get_response = self.client.get("/password-reset", query_string={"token": token})
                self.assertEqual(get_response.status_code, 200)
                self.assertIn("Reset your password", get_response.get_data(as_text=True))
                if account_type == "business":
                    self.assertIn("Coffee House", get_response.get_data(as_text=True))
                else:
                    self.assertIn("Ali Veli", get_response.get_data(as_text=True))

                post_response = self.client.post(
                    "/password-reset",
                    data={
                        "token": token,
                        "password": "NewPassword123!",
                        "confirm_password": "NewPassword123!",
                    },
                )
                self.assertEqual(post_response.status_code, 200)
                self.assertIn(
                    "Password has been reset successfully",
                    post_response.get_data(as_text=True),
                )
                updated_doc = target_collection.find_one({"_id": account_doc["_id"]})
                self.assertIsNotNone(updated_doc)
                self.assertTrue(verify_password("NewPassword123!", str(updated_doc["password_hash"])))

    def test_password_reset_submit_rejects_mismatched_passwords(self):
        account_doc = {
            "_id": ObjectId(),
            "name": "Coffee House",
            "email": "business@example.com",
            "password_hash": auth_helper.hash_password("OldPassword123!"),
        }
        self._install_account("business", account_doc)
        token = create_password_reset_token(str(account_doc["_id"]), "business")

        response = self.client.post(
            "/password-reset",
            data={
                "token": token,
                "password": "NewPassword123!",
                "confirm_password": "DifferentPassword123!",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Passwords do not match", response.get_data(as_text=True))

        updated_doc = self.business_collection.find_one({"_id": account_doc["_id"]})
        self.assertIsNotNone(updated_doc)
        self.assertTrue(verify_password("OldPassword123!", str(updated_doc["password_hash"])))


if __name__ == "__main__":
    unittest.main()





