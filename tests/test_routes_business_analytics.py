import datetime as dt
import os
import uuid
import unittest

from bson import ObjectId
from dotenv import load_dotenv


class BusinessAnalyticsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        os.environ["JWT_SECRET"] = "c" * 128
        os.environ["JWT_REFRESH_SECRET"] = "c" * 128
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
        cls.products = db["products"]
        cls.users = db["users"]
        cls.orders = db["orders"]

        try:
            cls.mongo_client.admin.command("ping")
        except Exception as exc:
            raise unittest.SkipTest(f"Mongo unavailable: {exc}") from exc

    @classmethod
    def tearDownClass(cls):
        pass  # MongoDB client is managed by conftest.py

    def setUp(self):
        self.created_business_emails = []
        self.created_business_ids = []
        self.created_category_ids = []
        self.created_product_ids = []
        self.created_user_emails = []
        self.created_order_ids = []

    def tearDown(self):
        if self.created_order_ids:
            self.orders.delete_many({"_id": {"$in": self.created_order_ids}})
        if self.created_product_ids:
            self.products.delete_many({"_id": {"$in": self.created_product_ids}})
        if self.created_category_ids:
            self.categories.delete_many({"_id": {"$in": self.created_category_ids}})
        if self.created_business_ids:
            self.categories.delete_many({"business_id": {"$in": self.created_business_ids}})
            self.products.delete_many({"business_id": {"$in": self.created_business_ids}})
            self.orders.delete_many({"business_id": {"$in": self.created_business_ids}})
        if self.created_business_emails:
            self.businesses.delete_many({"email": {"$in": self.created_business_emails}})
        if self.created_user_emails:
            self.users.delete_many({"email": {"$in": self.created_user_emails}})

    def _unique_email(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex}@example.com"

    def _register_business(self, email: str) -> tuple[str, str]:
        payload = {"name": "Test Business", "email": email, "password": "Password123!"}
        response = self.client.post("/api/v1/business/auth/register", json=payload)
        if response.status_code != 201:
            response_text = response.get_data(as_text=True)
            self.fail(f"Register failed: {response.status_code} {response_text}")
        data = response.get_json()
        self.created_business_emails.append(email)
        business_id = data["business"]["_id"]
        self.created_business_ids.append(ObjectId(business_id))
        return data["access_token"], business_id

    def _register_client(self, email: str) -> str:
        payload = {
            "first_name": "Test",
            "last_name": "Client",
            "phone_number": "1234567890",
            "email": email,
            "password": "Password123!",
        }
        response = self.client.post("/api/v1/client/auth/register", json=payload)
        if response.status_code != 201:
            response_text = response.get_data(as_text=True)
            self.fail(f"Register failed: {response.status_code} {response_text}")
        data = response.get_json()
        self.created_user_emails.append(email)
        return data["access_token"]

    def _create_category(self, access_token: str, name: str = "Test Category") -> str:
        response = self.client.post(
            "/api/v1/business/categories",
            json={"name": name},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 201:
            response_text = response.get_data(as_text=True)
            self.fail(f"Create category failed: {response.status_code} {response_text}")
        data = response.get_json()
        category_id = data["category"]["_id"]
        self.created_category_ids.append(ObjectId(category_id))
        return category_id

    def _create_product(self, access_token: str, category_id: str, name: str = "Test Product") -> str:
        response = self.client.post(
            "/api/v1/business/products",
            json={"name": name, "category_id": category_id, "price": "10.00"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 201:
            response_text = response.get_data(as_text=True)
            self.fail(f"Create product failed: {response.status_code} {response_text}")
        data = response.get_json()
        product_id = data["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))
        return product_id

    def _create_order(self, access_token: str, business_id: str, product_id: str, quantity: int = 1) -> str:
        response = self.client.post(
            "/api/v1/client/orders",
            json={"business_id": business_id, "items": [{"product_id": product_id, "quantity": quantity}]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 201:
            response_text = response.get_data(as_text=True)
            self.fail(f"Create order failed: {response.status_code} {response_text}")
        data = response.get_json()
        order_id = data["order"]["_id"]
        self.created_order_ids.append(ObjectId(order_id))
        return order_id

    def test_analytics_defaults_to_current_month(self):
        business_email = self._unique_email("biz")
        business_token, business_id = self._register_business(business_email)
        category_id = self._create_category(business_token)
        product_id = self._create_product(business_token, category_id)

        client_email = self._unique_email("client")
        client_token = self._register_client(client_email)

        recent_order_id = self._create_order(client_token, business_id, product_id, quantity=2)
        old_order_id = self._create_order(client_token, business_id, product_id, quantity=1)

        old_timestamp = dt.datetime.now(dt.UTC) - dt.timedelta(days=40)
        self.orders.update_one({"_id": ObjectId(old_order_id)}, {"$set": {"created_at": old_timestamp}})

        response = self.client.get(
            "/api/v1/business/analytics",
            headers={"Authorization": f"Bearer {business_token}"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload["total_orders"], 1)
        self.assertEqual(payload["total_items"], 2)
        self.assertAlmostEqual(payload["total_revenue"], 20.0)
        self.assertAlmostEqual(payload["average_order_value"], 20.0)
        self.assertTrue(payload["top_products"])
        self.assertTrue(payload["top_categories"])
        self.assertIsNotNone(payload["least_sold_category"])

    def test_analytics_custom_range_includes_old_order(self):
        business_email = self._unique_email("biz")
        business_token, business_id = self._register_business(business_email)
        category_id = self._create_category(business_token)
        product_id = self._create_product(business_token, category_id)

        client_email = self._unique_email("client")
        client_token = self._register_client(client_email)

        recent_order_id = self._create_order(client_token, business_id, product_id, quantity=2)
        old_order_id = self._create_order(client_token, business_id, product_id, quantity=1)

        old_timestamp = dt.datetime.now(dt.UTC) - dt.timedelta(days=40)
        self.orders.update_one({"_id": ObjectId(old_order_id)}, {"$set": {"created_at": old_timestamp}})

        from_dt = (dt.datetime.now(dt.UTC) - dt.timedelta(days=45)).isoformat()
        to_dt = dt.datetime.now(dt.UTC).isoformat()

        response = self.client.get(
            "/api/v1/business/analytics",
            query_string={"from": from_dt, "to": to_dt},
            headers={"Authorization": f"Bearer {business_token}"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload["total_orders"], 2)
        self.assertEqual(payload["total_items"], 3)
        self.assertAlmostEqual(payload["total_revenue"], 30.0)


if __name__ == "__main__":
    unittest.main()

