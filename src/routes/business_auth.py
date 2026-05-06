import datetime as dt
import os

import jwt
from bson import ObjectId
from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError

from src.middleware.auth_middleware import authenticate_request
from src.utils.auth_helper import (
    JWT_ALGORITHM,
    build_entity_response,
    create_access_token,
    create_refresh_token,
    hash_password,
    normalize_email,
    verify_password,
)
from src.utils.database_helper import db

business_auth_bp = Blueprint("business_auth", __name__)

BUSINESS_FIELDS = ["name", "email", "qr_base_url"]
businesses = db["businesses"]


@business_auth_bp.route("/register", methods=["POST"])
def register_business():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = normalize_email(data.get("email") or "")
    password = data.get("password") or ""
    qr_base_url = (data.get("qr_base_url") or "").strip() or None

    if not name or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        if businesses.find_one({"email": email}):
            return jsonify({"error": "Email already registered"}), 409

        business_doc = {
            "name": name,
            "email": email,
            "password_hash": hash_password(password),
            "qr_base_url": qr_base_url,
            "created_at": dt.datetime.now(dt.UTC),
        }
        result = businesses.insert_one(business_doc)
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    business_id = str(result.inserted_id)
    try:
        access_token = create_access_token(business_id, "business")
        refresh_token = create_refresh_token(business_id, "business")
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    business_doc["_id"] = result.inserted_id
    return (
        jsonify(
            {
                "business": build_entity_response(business_doc, BUSINESS_FIELDS),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        ),
        201,
    )


@business_auth_bp.route("/login", methods=["POST"])
def login_business():
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get("email") or "")
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        business_doc = businesses.find_one({"email": email})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not business_doc or not verify_password(password, business_doc.get("password_hash", "")):
        return jsonify({"error": "Invalid credentials"}), 401

    business_id = str(business_doc["_id"])
    try:
        access_token = create_access_token(business_id, "business")
        refresh_token = create_refresh_token(business_id, "business")
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    return (
        jsonify(
            {
                "business": build_entity_response(business_doc, BUSINESS_FIELDS),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        ),
        200,
    )


@business_auth_bp.route("/refresh", methods=["POST"])
def refresh_access_token():
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "Missing refresh token"}), 401

    secret = os.getenv("JWT_REFRESH_SECRET")
    if not secret:
        return jsonify({"error": "Server configuration error: Missing refresh secret"}), 500

    try:
        payload = jwt.decode(refresh_token, secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    if payload.get("user_type") != "business":
        return jsonify({"error": "Invalid token payload"}), 401

    business_id = payload.get("sub")
    if not business_id:
        return jsonify({"error": "Invalid token payload"}), 401

    try:
        mongo_id = ObjectId(business_id) if ObjectId.is_valid(business_id) else business_id
        business_doc = businesses.find_one({"_id": mongo_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not business_doc:
        return jsonify({"error": "Business not found"}), 401

    try:
        access_token = create_access_token(str(business_doc["_id"]), "business")
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"access_token": access_token}), 200


@business_auth_bp.route("/edit", methods=["PUT"])
def edit_business():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result

    if auth_result.get("user_type") != "business":
        return jsonify({"error": "Access forbidden"}), 403

    data = request.get_json(silent=True) or {}
    update_doc = {}

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Invalid name"}), 400
        update_doc["name"] = name

    if "email" in data:
        email = normalize_email(data.get("email") or "")
        if not email:
            return jsonify({"error": "Invalid email"}), 400
        update_doc["email"] = email

    if "password" in data:
        password = data.get("password") or ""
        if not password:
            return jsonify({"error": "Invalid password"}), 400
        update_doc["password_hash"] = hash_password(password)

    if "qr_base_url" in data:
        qr_base_url = (data.get("qr_base_url") or "").strip()
        update_doc["qr_base_url"] = qr_base_url or None

    if not update_doc:
        return jsonify({"error": "No changes provided"}), 400

    business_id = auth_result.get("_id")
    mongo_id = ObjectId(business_id) if ObjectId.is_valid(business_id) else business_id

    try:
        if "email" in update_doc:
            existing = businesses.find_one({"email": update_doc["email"], "_id": {"$ne": mongo_id}})
            if existing:
                return jsonify({"error": "Email already registered"}), 409

        businesses.update_one({"_id": mongo_id}, {"$set": update_doc})
        business_doc = businesses.find_one({"_id": mongo_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not business_doc:
        return jsonify({"error": "Business not found"}), 404

    return jsonify({"business": build_entity_response(business_doc, BUSINESS_FIELDS)}), 200


@business_auth_bp.route("/delete", methods=["DELETE"])
def delete_business():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result

    if auth_result.get("user_type") != "business":
        return jsonify({"error": "Access forbidden"}), 403

    business_id = auth_result.get("_id")
    mongo_id = ObjectId(business_id) if ObjectId.is_valid(business_id) else business_id

    try:
        delete_result = businesses.delete_one({"_id": mongo_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if delete_result.deleted_count == 0:
        return jsonify({"error": "Business not found"}), 404

    return jsonify({"message": "Business deleted"}), 200

