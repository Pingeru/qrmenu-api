import datetime as dt
import os
import unittest

import jwt

from src.utils import auth_helper


class AuthHelperTests(unittest.TestCase):
    def setUp(self):
        os.environ["JWT_SECRET"] = "test-access-secret"
        os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret"
        os.environ["ACCESS_TOKEN_TTL_MIN"] = "5"
        os.environ["REFRESH_TOKEN_TTL_DAYS"] = "5"

    def test_hash_and_verify_password(self):
        password = "pa55w0rd"
        password_hash = auth_helper.hash_password(password)
        self.assertTrue(auth_helper.verify_password(password, password_hash))
        self.assertFalse(auth_helper.verify_password("wrong", password_hash))

    def test_create_access_token(self):
        token = auth_helper.create_access_token("abc123", "client")
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[auth_helper.JWT_ALGORITHM])
        self.assertEqual(payload["sub"], "abc123")
        self.assertEqual(payload["user_type"], "client")

    def test_create_refresh_token(self):
        token = auth_helper.create_refresh_token("biz456", "business")
        payload = jwt.decode(token, os.environ["JWT_REFRESH_SECRET"], algorithms=[auth_helper.JWT_ALGORITHM])
        self.assertEqual(payload["sub"], "biz456")
        self.assertEqual(payload["user_type"], "business")

    def test_build_entity_response(self):
        created_at = dt.datetime(2026, 5, 6, 12, 0, 0)
        doc = {"_id": "abc", "email": "a@b.com", "created_at": created_at}
        response = auth_helper.build_entity_response(doc, ["email"])
        self.assertEqual(response["_id"], "abc")
        self.assertEqual(response["email"], "a@b.com")
        self.assertEqual(response["created_at"], created_at.isoformat())


if __name__ == "__main__":
    unittest.main()

