import datetime as dt
import os
from typing import Any

from src.routes.categories import delete_category_entry
from src.routes.products import delete_product_entry
from src.utils.database_helper import db

businesses = db["businesses"]
categories = db["categories"]
orders = db["orders"]
products = db["products"]
users = db["users"]


def delete_cancelled_orders_older_than(hours: int = 3) -> int:
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=hours)
    result = orders.delete_many({"status": "cancelled", "created_at": {"$lt": cutoff}})
    return result.deleted_count


def delete_orders_older_than_months(months: int = 3) -> int:
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=months * 30)
    result = orders.delete_many({"created_at": {"$lt": cutoff}})
    return result.deleted_count


def cleanup_orphaned_data(app_root_path: str) -> dict[str, Any]:
    deleted_images = _cleanup_orphaned_images(app_root_path)
    deleted_orders = _cleanup_orphaned_orders()
    deleted_products = _cleanup_orphaned_products()
    deleted_categories = _cleanup_orphaned_categories()
    return {
        "deleted_images": deleted_images,
        "deleted_orders": deleted_orders,
        "deleted_products": deleted_products,
        "deleted_categories": deleted_categories,
    }


def _cleanup_orphaned_images(app_root_path: str) -> int:
    images_dir = os.path.join(app_root_path, "static", "images")
    if not os.path.exists(images_dir):
        return 0

    referenced = set()
    for doc in products.find({"image_path": {"$ne": None}}, {"image_path": 1}):
        image_path = doc.get("image_path") or ""
        filename = os.path.basename(image_path.lstrip("/"))
        if filename:
            referenced.add(filename)

    deleted_count = 0
    for filename in os.listdir(images_dir):
        file_path = os.path.join(images_dir, filename)
        if not os.path.isfile(file_path):
            continue
        if filename not in referenced:
            try:
                os.remove(file_path)
                deleted_count += 1
            except OSError:
                continue

    return deleted_count


def _cleanup_orphaned_orders() -> int:
    business_ids = {doc["_id"] for doc in businesses.find({}, {"_id": 1})}
    user_ids = {doc["_id"] for doc in users.find({}, {"_id": 1})}

    deleted_count = 0
    for order_doc in orders.find({}, {"_id": 1, "business_id": 1, "user_id": 1}):
        business_id = order_doc.get("business_id")
        user_id = order_doc.get("user_id")
        if business_id not in business_ids or user_id not in user_ids:
            orders.delete_one({"_id": order_doc["_id"]})
            deleted_count += 1

    return deleted_count


def _cleanup_orphaned_products() -> int:
    business_ids = {doc["_id"] for doc in businesses.find({}, {"_id": 1})}
    category_map = {
        doc["_id"]: doc.get("business_id")
        for doc in categories.find({}, {"_id": 1, "business_id": 1})
    }

    deleted_count = 0
    for product_doc in products.find({}, {"_id": 1, "business_id": 1, "category_id": 1}):
        business_id = product_doc.get("business_id")
        category_id = product_doc.get("category_id")
        category_business_id = category_map.get(category_id)
        invalid_business = business_id not in business_ids
        invalid_category = category_business_id is None
        mismatched = category_business_id is not None and category_business_id != business_id

        if invalid_business or invalid_category or mismatched:
            delete_product_entry(product_doc["_id"], None)
            deleted_count += 1

    return deleted_count


def _cleanup_orphaned_categories() -> int:
    business_ids = {doc["_id"] for doc in businesses.find({}, {"_id": 1})}

    deleted_count = 0
    for category_doc in categories.find({}, {"_id": 1, "business_id": 1}):
        business_id = category_doc.get("business_id")
        if business_id not in business_ids:
            delete_category_entry(category_doc["_id"], None)
            deleted_count += 1

    return deleted_count

