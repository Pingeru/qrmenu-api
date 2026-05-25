import datetime as dt

from bson import ObjectId
from flask import Blueprint, jsonify, request
from nanoid import generate
from pymongo.errors import PyMongoError

from src.middleware.auth_middleware import authenticate_request
from src.utils.database_helper import db

client_orders_bp = Blueprint("client_orders", __name__)

orders = db["orders"]
products = db["products"]


def _require_client():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result, None

    if auth_result.get("user_type") != "client":
        return (jsonify({"error": "Access forbidden"}), 403), None

    user_id = auth_result.get("_id")
    mongo_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
    return None, mongo_id


def _parse_quantity(value):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return None
    if quantity <= 0:
        return None
    return quantity


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


@client_orders_bp.route("", methods=["POST"])
def create_order():
    auth_error, user_id = _require_client()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    business_id = data.get("business_id")
    table_number = (data.get("table_number") or "").strip()
    items = data.get("items")

    if not business_id or not table_number or not items:
        return jsonify({"error": "Missing required fields"}), 400

    if not ObjectId.is_valid(business_id):
        return jsonify({"error": "Invalid business id"}), 400

    if not isinstance(items, list):
        return jsonify({"error": "Invalid items"}), 400

    parsed_items = []
    product_ids = []
    for item in items:
        product_id = item.get("product_id") if isinstance(item, dict) else None
        quantity = _parse_quantity(item.get("quantity") if isinstance(item, dict) else None)
        if not product_id or quantity is None:
            return jsonify({"error": "Invalid item data"}), 400
        if not ObjectId.is_valid(product_id):
            return jsonify({"error": "Invalid product id"}), 400
        mongo_product_id = ObjectId(product_id)
        parsed_items.append({"product_id": mongo_product_id, "quantity": quantity})
        product_ids.append(mongo_product_id)

    unique_product_ids = list({pid for pid in product_ids})

    try:
        product_docs = list(
            products.find(
                {"_id": {"$in": unique_product_ids}, "business_id": ObjectId(business_id)}
            )
        )
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if len(product_docs) != len(unique_product_ids):
        return jsonify({"error": "Items must exist and belong to the same business"}), 400

    product_map = {str(doc["_id"]): doc for doc in product_docs}
    order_items = []
    total_amount = 0.0
    for item in parsed_items:
        product_doc = product_map.get(str(item["product_id"]))
        if not product_doc:
            return jsonify({"error": "Items must exist and belong to the same business"}), 400
        price = product_doc.get("price")
        if price is None:
            return jsonify({"error": "Invalid product price"}), 400
        item_total = float(price) * item["quantity"]
        total_amount += item_total
        order_items.append(
            {
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "price_at_purchase": float(price),
            }
        )

    order_doc = {
        "short_order_id": generate(size=8),
        "business_id": ObjectId(business_id),
        "user_id": user_id,
        "table_number": table_number,
        "items": order_items,
        "total_amount": float(total_amount),
        "status": "placed",
        "created_at": dt.datetime.now(dt.UTC),
    }

    try:
        result = orders.insert_one(order_doc)
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    order_doc["_id"] = result.inserted_id
    return jsonify({"order": _serialize_order(order_doc)}), 201


@client_orders_bp.route("", methods=["GET"])
def list_orders():
    auth_error, user_id = _require_client()
    if auth_error:
        return auth_error

    try:
        order_docs = list(orders.find({"user_id": user_id}).sort("created_at", -1))
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    return jsonify({"orders": [_serialize_order(order) for order in order_docs]}), 200


@client_orders_bp.route("/<order_id>", methods=["DELETE"])
def cancel_order(order_id: str):
    auth_error, user_id = _require_client()
    if auth_error:
        return auth_error

    if not ObjectId.is_valid(order_id):
        return jsonify({"error": "Invalid order id"}), 400

    mongo_id = ObjectId(order_id)
    try:
        order_doc = orders.find_one({"_id": mongo_id, "user_id": user_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not order_doc:
        return jsonify({"error": "Order not found"}), 404

    if order_doc.get("status") != "placed":
        return jsonify({"error": "Only placed orders can be cancelled"}), 400

    try:
        orders.update_one(
            {"_id": mongo_id, "user_id": user_id},
            {"$set": {"status": "cancelled"}},
        )
        order_doc = orders.find_one({"_id": mongo_id, "user_id": user_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    return jsonify({"order": _serialize_order(order_doc)}), 200

