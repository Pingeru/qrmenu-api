import datetime as dt
import os

import jwt
from bson import ObjectId
from flask import Blueprint, jsonify, request, current_app
from pymongo.errors import PyMongoError

from src.middleware.auth_middleware import authenticate_request
from src.routes.categories import delete_category_entry
from src.routes.products import delete_product_entry
from src.utils.auth_helper import (
    JWT_ALGORITHM,
    build_entity_response,
    create_access_token,
    create_refresh_token,
    hash_password,
    normalize_email,
    verify_password,
)
from src.utils.password_reset_helper import send_password_reset_email
from src.utils.database_helper import db

business_auth_bp = Blueprint("business_auth", __name__)

BUSINESS_FIELDS = ["name", "email"]
businesses = db["businesses"]
categories = db["categories"]
products = db["products"]
orders = db["orders"]


def delete_business_entry(business_id: str | ObjectId) -> bool:
    if isinstance(business_id, ObjectId):
        mongo_id = business_id
    elif ObjectId.is_valid(business_id):
        mongo_id = ObjectId(business_id)
    else:
        return False

    business_doc = businesses.find_one({"_id": mongo_id})
    if not business_doc:
        return False

    for category_doc in categories.find({"business_id": mongo_id}, {"_id": 1}):
        delete_category_entry(category_doc["_id"], mongo_id)

    for product_doc in products.find({"business_id": mongo_id}, {"_id": 1}):
        delete_product_entry(product_doc["_id"], mongo_id)

    orders.delete_many({"business_id": mongo_id})

    delete_result = businesses.delete_one({"_id": mongo_id})
    return delete_result.deleted_count > 0


@business_auth_bp.route("/register", methods=["POST"])
def register_business():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = normalize_email(data.get("email") or "")
    password = data.get("password") or ""
    if not name or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        if businesses.find_one({"email": email}):
            return jsonify({"error": "Email already registered"}), 409

        business_doc = {
            "name": name,
            "email": email,
            "password_hash": hash_password(password),
            "created_at": dt.datetime.now(dt.UTC),
        }
        result = businesses.insert_one(business_doc)
    except PyMongoError as exc:
        if current_app.testing:
            return jsonify({"error": "Database error occurred", "details": str(exc)}), 500
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


@business_auth_bp.route("/forgot-password", methods=["POST"])
def forgot_business_password():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    email = normalize_email(data.get("email") or "")

    if not email:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        business_doc = businesses.find_one({"email": email})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if business_doc:
        try:
            send_password_reset_email(business_doc, "business")
        except RuntimeError:
            return jsonify({"error": "Unable to send password reset email"}), 500

    return (
        jsonify({"message": "If the account exists, a password reset email has been sent"}),
        200,
    )


@business_auth_bp.route("/edit", methods=["PUT"])
def edit_business():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result

    if auth_result.get("user_type") != "business":
        return jsonify({"error": "Access forbidden"}), 403

    data = request.get_json(silent=True) or {}
    set_doc = {}
    unset_doc = {}

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Invalid name"}), 400
        set_doc["name"] = name

    if "email" in data:
        email = normalize_email(data.get("email") or "")
        if not email:
            return jsonify({"error": "Invalid email"}), 400
        set_doc["email"] = email

    if "password" in data:
        password = data.get("password") or ""
        if not password:
            return jsonify({"error": "Invalid password"}), 400
        set_doc["password_hash"] = hash_password(password)

    update_ops = {}
    if set_doc:
        update_ops["$set"] = set_doc
    if unset_doc:
        update_ops["$unset"] = unset_doc

    if not update_ops:
        return jsonify({"error": "No changes provided"}), 400

    business_id = auth_result.get("_id")
    mongo_id = ObjectId(business_id) if ObjectId.is_valid(business_id) else business_id

    try:
        if "email" in set_doc:
            existing = businesses.find_one({"email": set_doc["email"], "_id": {"$ne": mongo_id}})
            if existing:
                return jsonify({"error": "Email already registered"}), 409

        businesses.update_one({"_id": mongo_id}, update_ops)
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
        deleted = delete_business_entry(mongo_id)
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not deleted:
        return jsonify({"error": "Business not found"}), 404

    return jsonify({"message": "Business deleted"}), 200

