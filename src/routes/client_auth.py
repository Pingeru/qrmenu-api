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

client_auth_bp = Blueprint("client_auth", __name__)

CLIENT_FIELDS = ["first_name", "last_name", "phone_number", "email"]
users = db["users"]


@client_auth_bp.route("/register", methods=["POST"])
def register_client():
    data = request.get_json(silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    phone_number = (data.get("phone_number") or "").strip()
    email = normalize_email(data.get("email") or "")
    password = data.get("password") or ""

    if not first_name or not last_name or not phone_number or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        if users.find_one({"email": email}):
            return jsonify({"error": "Email already registered"}), 409

        user_doc = {
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
            "email": email,
            "password_hash": hash_password(password),
            "created_at": dt.datetime.now(dt.UTC),
        }
        result = users.insert_one(user_doc)
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    user_id = str(result.inserted_id)
    try:
        access_token = create_access_token(user_id, "client")
        refresh_token = create_refresh_token(user_id, "client")
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    user_doc["_id"] = result.inserted_id
    return (
        jsonify(
            {
                "user": build_entity_response(user_doc, CLIENT_FIELDS),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        ),
        201,
    )


@client_auth_bp.route("/login", methods=["POST"])
def login_client():
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get("email") or "")
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        user_doc = users.find_one({"email": email})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not user_doc or not verify_password(password, user_doc.get("password_hash", "")):
        return jsonify({"error": "Invalid credentials"}), 401

    user_id = str(user_doc["_id"])
    try:
        access_token = create_access_token(user_id, "client")
        refresh_token = create_refresh_token(user_id, "client")
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    return (
        jsonify(
            {
                "user": build_entity_response(user_doc, CLIENT_FIELDS),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        ),
        200,
    )


@client_auth_bp.route("/refresh", methods=["POST"])
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

    if payload.get("user_type") != "client":
        return jsonify({"error": "Invalid token payload"}), 401

    user_id = payload.get("sub")
    if not user_id:
        return jsonify({"error": "Invalid token payload"}), 401

    try:
        mongo_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
        user_doc = users.find_one({"_id": mongo_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not user_doc:
        return jsonify({"error": "User not found"}), 401

    try:
        access_token = create_access_token(str(user_doc["_id"]), "client")
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"access_token": access_token}), 200


@client_auth_bp.route("/edit", methods=["PUT"])
def edit_client():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result

    if auth_result.get("user_type") != "client":
        return jsonify({"error": "Access forbidden"}), 403

    data = request.get_json(silent=True) or {}
    update_doc = {}

    if "first_name" in data:
        first_name = (data.get("first_name") or "").strip()
        if not first_name:
            return jsonify({"error": "Invalid first name"}), 400
        update_doc["first_name"] = first_name

    if "last_name" in data:
        last_name = (data.get("last_name") or "").strip()
        if not last_name:
            return jsonify({"error": "Invalid last name"}), 400
        update_doc["last_name"] = last_name

    if "phone_number" in data:
        phone_number = (data.get("phone_number") or "").strip()
        if not phone_number:
            return jsonify({"error": "Invalid phone number"}), 400
        update_doc["phone_number"] = phone_number

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

    if not update_doc:
        return jsonify({"error": "No changes provided"}), 400

    user_id = auth_result.get("_id")
    mongo_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id

    try:
        if "email" in update_doc:
            existing = users.find_one({"email": update_doc["email"], "_id": {"$ne": mongo_id}})
            if existing:
                return jsonify({"error": "Email already registered"}), 409

        users.update_one({"_id": mongo_id}, {"$set": update_doc})
        user_doc = users.find_one({"_id": mongo_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not user_doc:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": build_entity_response(user_doc, CLIENT_FIELDS)}), 200


@client_auth_bp.route("/delete", methods=["DELETE"])
def delete_client():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result

    if auth_result.get("user_type") != "client":
        return jsonify({"error": "Access forbidden"}), 403

    user_id = auth_result.get("_id")
    mongo_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id

    try:
        delete_result = users.delete_one({"_id": mongo_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if delete_result.deleted_count == 0:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"message": "User deleted"}), 200

