import datetime as dt

from bson import ObjectId
from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError

from src.middleware.auth_middleware import authenticate_request
from src.utils.database_helper import db

business_orders_bp = Blueprint("business_orders", __name__)

orders = db["orders"]
products = db["products"]
users = db["users"]

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


def _normalize_id(value):
    if isinstance(value, ObjectId):
        return value
    if ObjectId.is_valid(value):
        return ObjectId(value)
    return value


def _build_image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    return f"{request.host_url.rstrip('/')}/{image_path.lstrip('/')}"


def _serialize_customer(user_doc: dict | None) -> dict | None:
    if not user_doc:
        return None

    first_name = (user_doc.get("first_name") or "").strip()
    last_name = (user_doc.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip()

    return {
        "id": str(user_doc.get("_id")),
        "name": full_name,
        "phone": user_doc.get("phone_number"),
    }

def _parse_iso_datetime(value: str) -> dt.datetime | None:
    if value is None:
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(v)
    except Exception:
        try:
            ts = float(value)
        except Exception:
            return None
        try:
            return dt.datetime.fromtimestamp(ts, dt.UTC)
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed


def _serialize_order(order_doc: dict, product_map: dict | None = None, user_map: dict | None = None) -> dict:
    created_at = order_doc.get("created_at")
    product_map = product_map or {}
    user_map = user_map or {}

    return {
        "_id": str(order_doc["_id"]),
        "short_order_id": order_doc.get("short_order_id"),
        "business_id": str(order_doc.get("business_id")),
        "user_id": str(order_doc.get("user_id")),
        "items": [
            {
                "product_id": str(item.get("product_id")),
                "product_name": (product_map.get(_normalize_id(item.get("product_id"))) or {}).get("name"),
                "product_image": _build_image_url((product_map.get(_normalize_id(item.get("product_id"))) or {}).get("image_path")),
                "quantity": item.get("quantity"),
                "price_at_purchase": item.get("price_at_purchase"),
            }
            for item in order_doc.get("items", [])
        ],
        "customer": _serialize_customer(user_map.get(_normalize_id(order_doc.get("user_id")))),
        "total_amount": order_doc.get("total_amount"),
        "status": order_doc.get("status"),
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
    }


@business_orders_bp.route("", methods=["GET"])
def list_business_orders():
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    now = dt.datetime.now(dt.UTC)
    default_cutoff = now - dt.timedelta(hours=12)

    from_raw = request.args.get("from")
    to_raw = request.args.get("to")

    from_dt = _parse_iso_datetime(from_raw) if from_raw is not None else None
    to_dt = _parse_iso_datetime(to_raw) if to_raw is not None else None

    if from_dt is None and to_dt is None:
        from_dt = default_cutoff
        to_dt = now
    elif from_dt is not None and to_dt is None:
        to_dt = now
    elif from_dt is None and to_dt is not None:
        from_dt = to_dt - dt.timedelta(hours=12)

    if from_dt is None or to_dt is None:
        return jsonify({"error": "Invalid date format for 'from' or 'to'"}), 400

    if from_dt > to_dt:
        return jsonify({"error": "'from' must be before or equal to 'to'"}), 400

    try:
        order_docs = list(
            orders.find(
                {"business_id": business_id, "created_at": {"$gte": from_dt, "$lte": to_dt}}
            ).sort("created_at", -1)
        )
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    product_ids = set()
    user_ids = set()
    for order_doc in order_docs:
        user_id = order_doc.get("user_id")
        if user_id is not None:
            user_ids.add(_normalize_id(user_id))
        for item in order_doc.get("items", []):
            product_id = item.get("product_id")
            if product_id is not None:
                product_ids.add(_normalize_id(product_id))

    try:
        product_docs = list(products.find({"_id": {"$in": list(product_ids)}})) if product_ids else []
        user_docs = list(users.find({"_id": {"$in": list(user_ids)}})) if user_ids else []
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    product_map = {doc["_id"]: doc for doc in product_docs}
    user_map = {doc["_id"]: doc for doc in user_docs}

    return jsonify({"orders": [_serialize_order(order, product_map, user_map) for order in order_docs]}), 200


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

