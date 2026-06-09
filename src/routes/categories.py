import datetime as dt

from bson import ObjectId
from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError

from src.middleware.auth_middleware import authenticate_request
from src.routes.products import delete_product_entry
from src.utils.database_helper import db, safe_insert

categories_bp = Blueprint("categories", __name__)

categories = db["categories"]
products = db["products"]


def delete_category_entry(category_id: str | ObjectId, business_id: ObjectId | None = None) -> bool:
    if isinstance(category_id, ObjectId):
        mongo_id = category_id
    elif ObjectId.is_valid(category_id):
        mongo_id = ObjectId(category_id)
    else:
        return False

    query = {"_id": mongo_id}
    if business_id is not None:
        query["business_id"] = business_id

    category_doc = categories.find_one(query)
    if not category_doc:
        return False

    product_query = {"category_id": mongo_id}
    if business_id is not None:
        product_query["business_id"] = business_id

    for product_doc in products.find(product_query, {"_id": 1}):
        delete_product_entry(product_doc["_id"], business_id)

    delete_result = categories.delete_one(query)
    return delete_result.deleted_count > 0


def _require_business():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result, None

    if auth_result.get("user_type") != "business":
        return (jsonify({"error": "Access forbidden"}), 403), None

    business_id = auth_result.get("_id")
    mongo_id = ObjectId(business_id) if ObjectId.is_valid(business_id) else business_id
    return None, mongo_id


def _get_optional_business_id():
    auth_header = request.headers.get("Authorization", "")
    body = request.get_json(silent=True) or {}
    if not auth_header and not body.get("access_token"):
        return None, None

    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result, None

    if auth_result.get("user_type") != "business":
        return None, None

    business_id = auth_result.get("_id")
    mongo_id = ObjectId(business_id) if ObjectId.is_valid(business_id) else business_id
    return None, mongo_id


def _serialize_category(category_doc: dict) -> dict:
    created_at = category_doc.get("created_at")
    return {
        "_id": str(category_doc["_id"]),
        "business_id": str(category_doc.get("business_id")),
        "name": category_doc.get("name"),
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
    }


@categories_bp.route("", methods=["POST"])
def create_category():
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Missing required fields"}), 400

    category_doc = {
        "business_id": business_id,
        "name": name,
        "created_at": dt.datetime.now(dt.UTC),
    }

    try:
        result = safe_insert(categories, category_doc)
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    category_doc["_id"] = result.inserted_id
    return jsonify({"category": _serialize_category(category_doc)}), 201


@categories_bp.route("", methods=["GET"])
def list_categories():
    auth_error, business_id = _get_optional_business_id()
    if auth_error:
        return auth_error

    query = {"business_id": business_id} if business_id is not None else {}

    try:
        category_docs = list(categories.find(query).sort("created_at", 1))
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    return (
        jsonify({"categories": [_serialize_category(category) for category in category_docs]}),
        200,
    )


@categories_bp.route("/<category_id>", methods=["GET"])
def get_category(category_id: str):
    if not ObjectId.is_valid(category_id):
        return jsonify({"error": "Invalid category id"}), 400

    auth_error, business_id = _get_optional_business_id()
    if auth_error:
        return auth_error

    mongo_id = ObjectId(category_id)
    try:
        category_doc = categories.find_one({"_id": mongo_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not category_doc:
        return jsonify({"error": "Category not found"}), 404

    if business_id is not None and category_doc.get("business_id") != business_id:
        return jsonify({"error": "Category not found"}), 404

    return jsonify({"category": _serialize_category(category_doc)}), 200


@categories_bp.route("/<category_id>", methods=["PUT"])
def update_category(category_id: str):
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    if not ObjectId.is_valid(category_id):
        return jsonify({"error": "Invalid category id"}), 400

    data = request.get_json(silent=True) or {}
    update_doc = {}

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Invalid name"}), 400
        update_doc["name"] = name

    if not update_doc:
        return jsonify({"error": "No changes provided"}), 400

    mongo_id = ObjectId(category_id)
    try:
        update_result = categories.update_one(
            {"_id": mongo_id, "business_id": business_id},
            {"$set": update_doc},
        )
        if update_result.matched_count == 0:
            return jsonify({"error": "Category not found"}), 404
        category_doc = categories.find_one({"_id": mongo_id, "business_id": business_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    return jsonify({"category": _serialize_category(category_doc)}), 200


@categories_bp.route("/<category_id>", methods=["DELETE"])
def delete_category(category_id: str):
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    if not ObjectId.is_valid(category_id):
        return jsonify({"error": "Invalid category id"}), 400

    try:
        deleted = delete_category_entry(category_id, business_id)
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not deleted:
        return jsonify({"error": "Category not found"}), 404

    return jsonify({"message": "Category deleted"}), 200
