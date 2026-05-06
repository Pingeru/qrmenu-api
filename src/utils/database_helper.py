import os
from urllib.parse import quote_plus, unquote_plus

from pymongo import MongoClient


def _maybe_quote(value: str) -> str:
    decoded = unquote_plus(value)
    reencoded = quote_plus(decoded)
    return value if reencoded == value else reencoded


def _sanitize_mongo_uri(uri: str) -> str:
    if not uri.startswith("mongodb://") or "@" not in uri:
        return uri

    _, rest = uri.split("mongodb://", 1)
    credentials, host_part = rest.split("@", 1)
    if ":" not in credentials:
        return uri

    username, password = credentials.split(":", 1)
    username = _maybe_quote(username)
    password = _maybe_quote(password)
    return f"mongodb://{username}:{password}@{host_part}"


MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_URI = _sanitize_mongo_uri(MONGO_URI)
DB_NAME = os.getenv("DB_NAME", "qrmb")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
