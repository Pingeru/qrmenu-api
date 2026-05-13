import os
import uuid
import unittest

from bson import ObjectId
from dotenv import load_dotenv


class CategoryRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        os.environ["JWT_SECRET"] = "test-access-secret"
        os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret"
        os.environ["ACCESS_TOKEN_TTL_MIN"] = "5"
        os.environ["REFRESH_TOKEN_TTL_DAYS"] = "5"
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        if "serverSelectionTimeoutMS" not in mongo_uri:
            separator = "&" if "?" in mongo_uri else "?"
            mongo_uri = f"{mongo_uri}{separator}serverSelectionTimeoutMS=2000"
        os.environ["MONGO_URI"] = mongo_uri
        try:
            from run import app
            from src.utils.database_helper import db, client
        except ImportError as exc:
            raise unittest.SkipTest(f"Dependencies unavailable: {exc}") from exc

        app.testing = True
        cls.client = app.test_client()
        cls.mongo_client = client
        cls.businesses = db["businesses"]
        cls.categories = db["categories"]
        try:
            cls.mongo_client.admin.command("ping")
        except Exception as exc:
            raise unittest.SkipTest(f"Mongo unavailable: {exc}") from exc

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "mongo_client", None):
            cls.mongo_client.close()

    def setUp(self):
        self.created_business_emails = []
        self.created_business_ids = []
        self.created_category_ids = []

    def tearDown(self):
        if self.created_category_ids:
            self.categories.delete_many({"_id": {"$in": self.created_category_ids}})
        if self.created_business_ids:
            self.categories.delete_many({"business_id": {"$in": self.created_business_ids}})
        if self.created_business_emails:
            self.businesses.delete_many({"email": {"$in": self.created_business_emails}})

    def _unique_email(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex}@example.com"

    def _register_business(self, email: str) -> tuple[str, str]:
        payload = {
            "name": "Test Business",
            "email": email,
            "password": "Password123!",
            "qr_base_url": "https://example.com/qr",
        }
        response = self.client.post("/api/v1/business/auth/register", json=payload)
        if response.status_code != 201:
            response_text = response.get_data(as_text=True)
            self.fail(f"Register failed: {response.status_code} {response_text}")
        data = response.get_json()
        self.created_business_emails.append(email)
        business_id = data["business"]["_id"]
        self.created_business_ids.append(ObjectId(business_id))
        return data["access_token"], business_id

    def test_category_crud_flow(self):
        email = self._unique_email("biz")
        access_token, business_id = self._register_business(email)

        create_response = self.client.post(
            "/api/v1/business/categories",
            json={"name": "Appetizers"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(create_response.status_code, 201)
        create_data = create_response.get_json()
        category_id = create_data["category"]["_id"]
        if ObjectId.is_valid(category_id):
            self.created_category_ids.append(ObjectId(category_id))
        self.assertEqual(create_data["category"]["business_id"], business_id)

        list_response = self.client.get(
            "/api/v1/business/categories",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(list_response.status_code, 200)
        list_data = list_response.get_json()
        self.assertTrue(any(cat["_id"] == category_id for cat in list_data["categories"]))

        get_response = self.client.get(
            f"/api/v1/business/categories/{category_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(get_response.status_code, 200)
        get_data = get_response.get_json()
        self.assertEqual(get_data["category"]["name"], "Appetizers")

        update_response = self.client.put(
            f"/api/v1/business/categories/{category_id}",
            json={"name": "Starters"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(update_response.status_code, 200)
        update_data = update_response.get_json()
        self.assertEqual(update_data["category"]["name"], "Starters")

        other_email = self._unique_email("biz")
        other_token, _ = self._register_business(other_email)
        forbidden_response = self.client.get(
            f"/api/v1/business/categories/{category_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        self.assertEqual(forbidden_response.status_code, 404)

        delete_response = self.client.delete(
            f"/api/v1/business/categories/{category_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(delete_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
