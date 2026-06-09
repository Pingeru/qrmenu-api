import os

import jwt
from bson import ObjectId
from flask import jsonify, request
from pymongo.errors import PyMongoError

from src.utils.database_helper import db

JWT_ALGORITHM = "HS256"


def authenticate_request():
    body = request.get_json(silent=True) or {}
    access_token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        if auth_header.startswith("Bearer "):
            access_token = auth_header.removeprefix("Bearer ").strip()
        else:
            return jsonify({"error": "Invalid authorization header"}), 401

    if not access_token:
        access_token = body.get("access_token")
    if not access_token:
        return jsonify({"error": "Missing access token"}), 401

    secret = os.getenv("JWT_SECRET")
    if not secret:
        return jsonify({"error": "Server configuration error: Missing JWT secret"}), 500

    try:
        payload = jwt.decode(access_token, secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    user_type = payload.get("user_type")
    user_id = payload.get("user_id") or payload.get("sub")
    if user_type not in ("client", "business") or not user_id:
        return jsonify({"error": "Invalid token payload"}), 401

    collection = db["users"] if user_type == "client" else db["businesses"]

    try:
        mongo_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
        user_doc = collection.find_one({"_id": mongo_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not user_doc:
        try:
            import importlib

            if user_type == "business":
                mod = importlib.import_module("src.routes.business_auth")
                alt_coll = getattr(mod, "businesses", None)
            else:
                mod = importlib.import_module("src.routes.client_auth")
                alt_coll = getattr(mod, "users", None)

            if alt_coll is not None:
                alt_find = getattr(alt_coll, "find_one", None)
                if callable(alt_find):
                    try:
                        user_doc = alt_find({"_id": mongo_id})
                    except Exception:
                        user_doc = None
        except Exception:
            # Import or lookup failed; fall through to not found
            user_doc = None

    if not user_doc:
        return jsonify({"error": "User not found"}), 401

    user_doc["_id"] = str(user_doc["_id"])
    user_doc["user_type"] = user_type
    return user_doc
