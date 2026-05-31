import datetime as dt

from bson import ObjectId
from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError

from src.middleware.auth_middleware import authenticate_request
from src.utils.database_helper import db

business_analytics_bp = Blueprint("business_analytics", __name__)

orders = db["orders"]
products = db["products"]
categories = db["categories"]


def _require_business():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result, None

    if auth_result.get("user_type") != "business":
        return (jsonify({"error": "Access forbidden"}), 403), None

    business_id = auth_result.get("_id")
    mongo_id = ObjectId(business_id) if ObjectId.is_valid(business_id) else business_id
    return None, mongo_id


def _build_image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    return f"{request.host_url.rstrip('/')}/{image_path.lstrip('/')}"


def _serialize_product(product_doc: dict, sold_quantity: int, sold_revenue: float) -> dict:
    created_at = product_doc.get("created_at")
    return {
        "product": {
            "_id": str(product_doc.get("_id")),
            "business_id": str(product_doc.get("business_id")),
            "category_id": str(product_doc.get("category_id")),
            "name": product_doc.get("name"),
            "description": product_doc.get("description"),
            "price": product_doc.get("price"),
            "image_path": _build_image_url(product_doc.get("image_path")),
            "is_active": product_doc.get("is_active"),
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        },
        "sold_quantity": sold_quantity,
        "sold_revenue": sold_revenue,
    }


def _serialize_category(category_doc: dict, sold_quantity: int, sold_revenue: float) -> dict:
    created_at = category_doc.get("created_at")
    return {
        "category": {
            "_id": str(category_doc.get("_id")),
            "business_id": str(category_doc.get("business_id")),
            "name": category_doc.get("name"),
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        },
        "sold_quantity": sold_quantity,
        "sold_revenue": sold_revenue,
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


@business_analytics_bp.route("", methods=["GET"])
def business_analytics():
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    now = dt.datetime.now(dt.UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    from_raw = request.args.get("from")
    to_raw = request.args.get("to")

    from_dt = _parse_iso_datetime(from_raw) if from_raw is not None else None
    to_dt = _parse_iso_datetime(to_raw) if to_raw is not None else None

    if from_dt is None and to_dt is None:
        from_dt = month_start
        to_dt = now
    elif from_dt is not None and to_dt is None:
        to_dt = now
    elif from_dt is None and to_dt is not None:
        from_dt = month_start

    if from_dt is None or to_dt is None:
        return jsonify({"error": "Invalid date format for 'from' or 'to'"}), 400

    if from_dt > to_dt:
        return jsonify({"error": "'from' must be before or equal to 'to'"}), 400

    order_match = {"business_id": business_id, "created_at": {"$gte": from_dt, "$lte": to_dt}}

    try:
        order_docs = list(orders.find(order_match, {"total_amount": 1, "items": 1}))
        product_docs = list(products.find({"business_id": business_id}))
        category_docs = list(categories.find({"business_id": business_id}))
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    total_orders = len(order_docs)
    total_revenue = 0.0
    total_items = 0

    product_sales = {}

    for order_doc in order_docs:
        total_revenue += float(order_doc.get("total_amount") or 0.0)
        for item in order_doc.get("items", []):
            product_id = item.get("product_id")
            quantity = int(item.get("quantity") or 0)
            price = float(item.get("price_at_purchase") or 0.0)
            total_items += quantity

            if product_id is None:
                continue
            stats = product_sales.setdefault(product_id, {"quantity": 0, "revenue": 0.0})
            stats["quantity"] += quantity
            stats["revenue"] += quantity * price

    avg_order_value = (total_revenue / total_orders) if total_orders else 0.0

    product_entries = []
    product_category_map = {}
    for product_doc in product_docs:
        product_id = product_doc.get("_id")
        product_category_map[product_id] = product_doc.get("category_id")
        stats = product_sales.get(product_id, {"quantity": 0, "revenue": 0.0})
        product_entries.append(
            _serialize_product(product_doc, int(stats["quantity"]), float(stats["revenue"]))
        )

    top_products = sorted(
        product_entries,
        key=lambda p: (-p["sold_quantity"], -p["sold_revenue"], p["product"].get("name") or ""),
    )
    least_sold_products = sorted(
        product_entries,
        key=lambda p: (p["sold_quantity"], p["sold_revenue"], p["product"].get("name") or ""),
    )

    category_sales = {}
    for product_id, stats in product_sales.items():
        category_id = product_category_map.get(product_id)
        if category_id is None:
            continue
        category_stats = category_sales.setdefault(category_id, {"quantity": 0, "revenue": 0.0})
        category_stats["quantity"] += stats["quantity"]
        category_stats["revenue"] += stats["revenue"]

    category_entries = []
    for category_doc in category_docs:
        category_id = category_doc.get("_id")
        stats = category_sales.get(category_id, {"quantity": 0, "revenue": 0.0})
        category_entries.append(
            _serialize_category(category_doc, int(stats["quantity"]), float(stats["revenue"]))
        )

    top_categories = sorted(
        category_entries,
        key=lambda c: (-c["sold_quantity"], -c["sold_revenue"], c["category"].get("name") or ""),
    )
    least_sold_category = None
    if category_entries:
        least_sold_category = sorted(
            category_entries,
            key=lambda c: (c["sold_quantity"], c["sold_revenue"], c["category"].get("name") or ""),
        )[0]

    return (
        jsonify(
            {
                "from": from_dt.isoformat(),
                "to": to_dt.isoformat(),
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "average_order_value": avg_order_value,
                "total_items": total_items,
                "top_categories": top_categories,
                "top_products": top_products,
                "least_sold_products": least_sold_products,
                "least_sold_category": least_sold_category,
            }
        ),
        200,
    )


