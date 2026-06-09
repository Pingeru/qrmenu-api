import os
from urllib.parse import quote_plus, unquote_plus

from bson import ObjectId
from pymongo import MongoClient



class _SafeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


def safe_insert(collection, doc: dict):
    """Insert a document using a real PyMongo collection if available,
    otherwise emulate insert_one for lightweight FakeCollection objects
    used in tests.

    Returns an object with an `inserted_id` attribute.
    """
    # Prefer real insert_one when present
    insert = getattr(collection, "insert_one", None)
    if callable(insert):
        return insert(doc)

    # Fallback for FakeCollection objects used in tests: append to .docs
    docs = getattr(collection, "docs", None)
    if docs is None:
        raise AttributeError("Collection does not support insert_one and has no .docs fallback")

    # Ensure we don't mutate caller's dict
    new_doc = dict(doc)
    if "_id" not in new_doc:
        new_doc["_id"] = ObjectId()
    docs.append(new_doc)
    return _SafeInsertResult(new_doc["_id"])


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
