import base64
import binascii
import datetime as dt
import hashlib
import hmac
import os

import jwt

JWT_ALGORITHM = "HS256"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return f"{salt_b64}.${digest_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_b64, digest_b64 = password_hash.split(".", 1)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
    except (ValueError, binascii.Error):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return hmac.compare_digest(actual, expected)


def create_access_token(subject_id: str, user_type: str) -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("Missing JWT_SECRET")

    ttl_minutes = int(os.getenv("ACCESS_TOKEN_TTL_MIN", "15"))
    payload = {
        "sub": subject_id,
        "user_type": user_type,
        "exp": dt.datetime.now(dt.UTC) + dt.timedelta(minutes=ttl_minutes),
    }
    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    return token.decode("utf-8") if isinstance(token, bytes) else token


def create_refresh_token(subject_id: str, user_type: str) -> str:
    secret = os.getenv("JWT_REFRESH_SECRET")
    if not secret:
        raise RuntimeError("Missing JWT_REFRESH_SECRET")

    ttl_days = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))
    payload = {
        "sub": subject_id,
        "user_type": user_type,
        "exp": dt.datetime.now(dt.UTC) + dt.timedelta(days=ttl_days),
    }
    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    return token.decode("utf-8") if isinstance(token, bytes) else token


def build_entity_response(entity_doc: dict, fields: list[str]) -> dict:
    created_at = entity_doc.get("created_at")
    created_at_value = created_at.isoformat() if hasattr(created_at, "isoformat") else created_at
    response = {"_id": str(entity_doc["_id"])}
    for field in fields:
        response[field] = entity_doc.get(field)
    if "created_at" in entity_doc:
        response["created_at"] = created_at_value
    return response

