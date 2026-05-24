import os
import uuid
import unittest
from io import BytesIO

from bson import ObjectId
from dotenv import load_dotenv


class ProductRouteTests(unittest.TestCase):
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
        cls.products = db["products"]
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

    def tearDown(self):
        if self.created_product_ids:
            self.products.delete_many({"_id": {"$in": self.created_product_ids}})
        if self.created_category_ids:
            self.categories.delete_many({"_id": {"$in": self.created_category_ids}})
        if self.created_business_ids:
            self.categories.delete_many({"business_id": {"$in": self.created_business_ids}})
            self.products.delete_many({"business_id": {"$in": self.created_business_ids}})
        if self.created_business_emails:
            self.businesses.delete_many({"email": {"$in": self.created_business_emails}})

        self.created_product_ids.clear()
        self.created_category_ids.clear()
        self.created_business_ids.clear()
        self.created_business_emails.clear()

    def _unique_email(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex}@example.com"

    def _register_business(self, email: str) -> tuple[str, str]:
        payload = {
            "name": "Test Business",
            "email": email,
            "password": "Password123!",
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

    def _create_test_image(self) -> BytesIO:
        img = BytesIO()
        img.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
        img.seek(0)
        return img

    def test_create_product_without_auth_returns_unauthorized(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": "Bearer invalid_token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_create_product_with_missing_name_returns_bad_request(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_create_product_with_missing_category_id_returns_bad_request(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_product_with_missing_price_returns_bad_request(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_product_with_invalid_category_id_returns_bad_request(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": "invalid_id",
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_product_with_invalid_price_returns_bad_request(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "not_a_number",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_product_without_image_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "description": "A test product",
                "category_id": category_id,
                "price": "10.99",
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn("product", data)
        product = data["product"]
        self.assertEqual(product["name"], "Test Product")
        self.assertEqual(product["price"], 10.99)
        self.assertIsNone(product["image_path"])
        self.assertTrue(product["is_active"])
        self.created_product_ids.append(ObjectId(product["_id"]))

    def test_create_product_with_image_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            data={
                "name": "Test Product",
                "category_id": category_id,
                "price": "15.50",
                "image": (self._create_test_image(), "test.png"),
            },
            headers={"Authorization": f"Bearer {access_token}"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        product = data["product"]
        self.assertEqual(product["name"], "Test Product")
        self.assertIsNotNone(product["image_path"])
        self.assertIn("static/images", product["image_path"])
        self.created_product_ids.append(ObjectId(product["_id"]))

    def test_create_product_with_default_is_active_is_true(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 201)
        product = response.get_json()["product"]
        self.assertTrue(product["is_active"])
        self.created_product_ids.append(ObjectId(product["_id"]))

    def test_create_product_with_is_active_false_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
                "is_active": False,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 201)
        product = response.get_json()["product"]
        self.assertFalse(product["is_active"])
        self.created_product_ids.append(ObjectId(product["_id"]))

    def test_get_product_by_id_returns_product(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.get(f"/api/v1/business/products/{product_id}")
        self.assertEqual(response.status_code, 200)
        product = response.get_json()["product"]
        self.assertEqual(product["_id"], product_id)
        self.assertEqual(product["name"], "Test Product")

    def test_get_product_with_invalid_id_returns_bad_request(self):
        response = self.client.get("/api/v1/business/products/invalid_id")
        self.assertEqual(response.status_code, 400)

    def test_get_product_that_does_not_exist_returns_not_found(self):
        response = self.client.get(f"/api/v1/business/products/{ObjectId()}")
        self.assertEqual(response.status_code, 404)

    def test_list_products_by_category_returns_products(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Product 1",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Product 2",
                "category_id": category_id,
                "price": "20.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        response = self.client.get(f"/api/v1/business/products/category/{category_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data["products"]), 2)
        self.created_product_ids.extend([ObjectId(p["_id"]) for p in data["products"]])

    def test_list_products_by_category_with_invalid_id_returns_bad_request(self):
        response = self.client.get("/api/v1/business/products/category/invalid_id")
        self.assertEqual(response.status_code, 400)

    def test_list_products_by_empty_category_returns_empty_list(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.get(f"/api/v1/business/products/category/{category_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data["products"]), 0)

    def test_update_product_without_auth_returns_unauthorized(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.put(
            f"/api/v1/business/products/{product_id}",
            json={"name": "Updated Product"},
            headers={"Authorization": "Bearer invalid_token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_update_product_name_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.put(
            f"/api/v1/business/products/{product_id}",
            json={"name": "Updated Product"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 200)
        product = response.get_json()["product"]
        self.assertEqual(product["name"], "Updated Product")

    def test_update_product_price_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.put(
            f"/api/v1/business/products/{product_id}",
            json={"price": "20.99"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 200)
        product = response.get_json()["product"]
        self.assertEqual(product["price"], 20.99)

    def test_update_product_is_active_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.put(
            f"/api/v1/business/products/{product_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 200)
        product = response.get_json()["product"]
        self.assertFalse(product["is_active"])

    def test_update_product_with_invalid_price_returns_bad_request(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.put(
            f"/api/v1/business/products/{product_id}",
            json={"price": "not_a_number"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_update_product_with_invalid_category_id_returns_bad_request(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.put(
            f"/api/v1/business/products/{product_id}",
            json={"category_id": "invalid_id"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_update_product_image_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.put(
            f"/api/v1/business/products/{product_id}",
            data={
                "image": (self._create_test_image(), "test.png"),
            },
            headers={"Authorization": f"Bearer {access_token}"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        product = response.get_json()["product"]
        self.assertIsNotNone(product["image_path"])

    def test_update_product_with_no_changes_returns_bad_request(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.put(
            f"/api/v1/business/products/{product_id}",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_update_nonexistent_product_returns_not_found(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)

        response = self.client.put(
            f"/api/v1/business/products/{ObjectId()}",
            json={"name": "Updated Product"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 404)

    def test_update_product_from_different_business_returns_not_found(self):
        email1 = self._unique_email("biz1")
        access_token1, _ = self._register_business(email1)
        category_id = self._create_category(access_token1)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token1}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        email2 = self._unique_email("biz2")
        access_token2, _ = self._register_business(email2)

        response = self.client.put(
            f"/api/v1/business/products/{product_id}",
            json={"name": "Updated Product"},
            headers={"Authorization": f"Bearer {access_token2}"},
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_product_without_auth_returns_unauthorized(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        response = self.client.delete(
            f"/api/v1/business/products/{product_id}",
            headers={"Authorization": "Bearer invalid_token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_delete_product_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product_id = create_response.get_json()["product"]["_id"]

        response = self.client.delete(
            f"/api/v1/business/products/{product_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.get_json())

    def test_delete_nonexistent_product_returns_not_found(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)

        response = self.client.delete(
            f"/api/v1/business/products/{ObjectId()}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_product_from_different_business_returns_not_found(self):
        email1 = self._unique_email("biz1")
        access_token1, _ = self._register_business(email1)
        category_id = self._create_category(access_token1)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token1}"},
        )
        product_id = create_response.get_json()["product"]["_id"]
        self.created_product_ids.append(ObjectId(product_id))

        email2 = self._unique_email("biz2")
        access_token2, _ = self._register_business(email2)

        response = self.client.delete(
            f"/api/v1/business/products/{product_id}",
            headers={"Authorization": f"Bearer {access_token2}"},
        )
        self.assertEqual(response.status_code, 404)

    def test_product_image_url_is_absolute_static_path(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            data={
                "name": "Test Product",
                "category_id": category_id,
                "price": "10.99",
                "image": (self._create_test_image(), "test.png"),
            },
            headers={"Authorization": f"Bearer {access_token}"},
            content_type="multipart/form-data",
        )
        product = response.get_json()["product"]
        self.created_product_ids.append(ObjectId(product["_id"]))

        self.assertIsNotNone(product["image_path"])
        self.assertTrue(product["image_path"].startswith("http"))
        self.assertIn("static/images", product["image_path"])

    def test_product_response_contains_all_required_fields(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        create_response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Test Product",
                "description": "Description",
                "category_id": category_id,
                "price": "10.99",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        product = create_response.get_json()["product"]
        self.created_product_ids.append(ObjectId(product["_id"]))

        required_fields = ["_id", "business_id", "category_id", "name", "description", "price", "image_path", "is_active", "created_at"]
        for field in required_fields:
            self.assertIn(field, product)

    def test_create_product_with_zero_price_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Free Product",
                "category_id": category_id,
                "price": 0,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 201)
        product = response.get_json()["product"]
        self.assertEqual(product["price"], 0.0)
        self.created_product_ids.append(ObjectId(product["_id"]))

    def test_create_product_with_large_price_succeeds(self):
        email = self._unique_email("biz")
        access_token, _ = self._register_business(email)
        category_id = self._create_category(access_token)

        response = self.client.post(
            "/api/v1/business/products",
            json={
                "name": "Expensive Product",
                "category_id": category_id,
                "price": 99999.99,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(response.status_code, 201)
        product = response.get_json()["product"]
        self.assertEqual(product["price"], 99999.99)
        self.created_product_ids.append(ObjectId(product["_id"]))


if __name__ == "__main__":
    unittest.main()

