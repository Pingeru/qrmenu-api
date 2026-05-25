import datetime as dt

from bson import ObjectId
from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError

from src.middleware.auth_middleware import authenticate_request
from src.utils.database_helper import db

business_orders_bp = Blueprint("business_orders", __name__)

orders = db["orders"]

ALLOWED_STATUSES = {"placed", "preparing", "ready", "cancelled"}


def _require_business():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result, None

    if auth_result.get("user_type") != "business":
        return (jsonify({"error": "Access forbidden"}), 403), None

    business_id = auth_result.get("_id")
    mongo_id = ObjectId(business_id) if ObjectId.is_valid(business_id) else business_id
    return None, mongo_id


def _serialize_order(order_doc: dict) -> dict:
    created_at = order_doc.get("created_at")
    return {
        "_id": str(order_doc["_id"]),
        "short_order_id": order_doc.get("short_order_id"),
        "business_id": str(order_doc.get("business_id")),
        "user_id": str(order_doc.get("user_id")),
        "table_number": order_doc.get("table_number"),
        "items": [
            {
                "product_id": str(item.get("product_id")),
                "quantity": item.get("quantity"),
                "price_at_purchase": item.get("price_at_purchase"),
            }
            for item in order_doc.get("items", [])
        ],
        "total_amount": order_doc.get("total_amount"),
        "status": order_doc.get("status"),
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
    }


@business_orders_bp.route("", methods=["GET"])
def list_business_orders():
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=12)
    try:
        order_docs = list(
            orders.find(
                {"business_id": business_id, "created_at": {"$gte": cutoff}}
            ).sort("created_at", -1)
        )
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    return jsonify({"orders": [_serialize_order(order) for order in order_docs]}), 200


@business_orders_bp.route("/<order_id>", methods=["PUT"])
def update_order_status(order_id: str):
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    if not ObjectId.is_valid(order_id):
        return jsonify({"error": "Invalid order id"}), 400

    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in ALLOWED_STATUSES:
        return jsonify({"error": "Invalid status"}), 400

    mongo_id = ObjectId(order_id)
    try:
        update_result = orders.update_one(
            {"_id": mongo_id, "business_id": business_id},
            {"$set": {"status": status}},
        )
        if update_result.matched_count == 0:
            return jsonify({"error": "Order not found"}), 404
        order_doc = orders.find_one({"_id": mongo_id, "business_id": business_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    return jsonify({"order": _serialize_order(order_doc)}), 200


@business_orders_bp.route("/<order_id>", methods=["DELETE"])
def delete_order(order_id: str):
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    if not ObjectId.is_valid(order_id):
        return jsonify({"error": "Invalid order id"}), 400

    mongo_id = ObjectId(order_id)
    try:
        delete_result = orders.delete_one({"_id": mongo_id, "business_id": business_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if delete_result.deleted_count == 0:
        return jsonify({"error": "Order not found"}), 404

    return jsonify({"message": "Order deleted"}), 200

