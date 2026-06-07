import datetime as dt
import os

from bson import ObjectId
from flask import Blueprint, jsonify, request, current_app
from nanoid import generate
from pymongo.errors import PyMongoError

from src.middleware.auth_middleware import authenticate_request
from src.utils.database_helper import db

products_bp = Blueprint("products", __name__)

products = db["products"]


def delete_product_entry(product_id: str | ObjectId, business_id: ObjectId | None = None) -> bool:
    if isinstance(product_id, ObjectId):
        mongo_id = product_id
    elif ObjectId.is_valid(product_id):
        mongo_id = ObjectId(product_id)
    else:
        return False

    query = {"_id": mongo_id}
    if business_id is not None:
        query["business_id"] = business_id

    product_doc = products.find_one(query)
    if not product_doc:
        return False

    delete_result = products.delete_one(query)
    if delete_result.deleted_count == 0:
        return False

    _delete_all_product_images(str(mongo_id))
    return True


def _require_business():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result, None

    if auth_result.get("user_type") != "business":
        return (jsonify({"error": "Access forbidden"}), 403), None

    business_id = auth_result.get("_id")
    mongo_id = ObjectId(business_id) if ObjectId.is_valid(business_id) else business_id
    return None, mongo_id


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _parse_price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_payload():
    if request.mimetype and request.mimetype.startswith("multipart/form-data"):
        return request.form.to_dict()
    return request.get_json(silent=True) or {}


def _parse_object_id_filter(value: str | None, field_name: str):
    if value is None:
        return None, None
    if not ObjectId.is_valid(value):
        return None, (jsonify({"error": f"Invalid {field_name}"}), 400)
    return ObjectId(value), None


def _save_image(product_id: str, image_file) -> str:
    root_path = str(current_app.root_path)
    images_dir = os.path.join(root_path, "static", "images")
    os.makedirs(images_dir, exist_ok=True)
    image_filename = f"{product_id}_{generate(size=10)}.png"
    image_path = os.path.join(images_dir, image_filename)
    image_file.save(image_path)
    return f"static/images/{image_filename}"


def _delete_image(image_path: str | None) -> None:
    if not image_path:
        return
    root_path = str(current_app.root_path)
    local_path = os.path.join(root_path, image_path.lstrip("/"))
    try:
        if os.path.exists(local_path):
            os.remove(local_path)
    except OSError:
        pass


def _delete_all_product_images(product_id: str) -> None:
    """Delete all images associated with a product (handles multiple versions)."""
    root_path = str(current_app.root_path)
    images_dir = os.path.join(root_path, "static", "images")
    if not os.path.exists(images_dir):
        return

    try:
        for filename in os.listdir(images_dir):
            if filename.startswith(f"{product_id}_"):
                filepath = os.path.join(images_dir, filename)
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except OSError:
                    pass
    except OSError:
        pass


def _build_image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    relative_path = image_path.lstrip("/")
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.headers.get("X-Forwarded-Host", request.host)
    return f"{proto}://{host}/{relative_path}"


def _serialize_product(product_doc: dict) -> dict:
    created_at = product_doc.get("created_at")
    return {
        "_id": str(product_doc["_id"]),
        "business_id": str(product_doc.get("business_id")),
        "category_id": str(product_doc.get("category_id")),
        "name": product_doc.get("name"),
        "description": product_doc.get("description"),
        "price": product_doc.get("price"),
        "image_path": _build_image_url(product_doc.get("image_path")),
        "is_active": product_doc.get("is_active"),
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
    }


@products_bp.route("", methods=["POST"])
def create_product():
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    data = _get_payload()
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    category_id = data.get("category_id")
    price_value = data.get("price")
    is_active = _parse_bool(data.get("is_active"))
    image_file = request.files.get("image")

    if not name or not category_id or price_value in (None, ""):
        return jsonify({"error": "Missing required fields"}), 400

    if not ObjectId.is_valid(category_id):
        return jsonify({"error": "Invalid category id"}), 400

    price = _parse_price(price_value)
    if price is None:
        return jsonify({"error": "Invalid price"}), 400

    if is_active is None:
        is_active = True

    # image upload is optional on create; it can be added later via update

    product_doc = {
        "business_id": business_id,
        "category_id": ObjectId(category_id),
        "name": name,
        "description": description,
        "price": price,
        "image_path": None,
        "is_active": is_active,
        "created_at": dt.datetime.now(dt.UTC),
    }

    inserted_id = None
    image_path = None
    try:
        result = products.insert_one(product_doc)
        inserted_id = result.inserted_id
        # Save image only if provided
        if image_file and image_file.filename:
            image_path = _save_image(str(inserted_id), image_file)
            products.update_one({"_id": inserted_id}, {"$set": {"image_path": image_path}})
    except PyMongoError:
        if image_path:
            _delete_image(image_path)
        if inserted_id:
            products.delete_one({"_id": inserted_id})
        return jsonify({"error": "Database error occurred"}), 500
    except OSError:
        if inserted_id:
            products.delete_one({"_id": inserted_id})
        return jsonify({"error": "File storage error occurred"}), 500

    product_doc["_id"] = inserted_id
    product_doc["image_path"] = image_path
    return jsonify({"product": _serialize_product(product_doc)}), 201



@products_bp.route("", methods=["GET"])
def list_products():
    category_id_raw = request.args.get("category_id")
    business_id_raw = request.args.get("business_id")
    is_active_raw = request.args.get("is_active")

    category_id, error_response = _parse_object_id_filter(category_id_raw, "category id")
    if error_response:
        return error_response

    business_id, error_response = _parse_object_id_filter(business_id_raw, "business id")
    if error_response:
        return error_response

    is_active = None
    if is_active_raw is not None:
        is_active = _parse_bool(is_active_raw)
        if is_active is None and is_active_raw.strip() != "":
            return jsonify({"error": "Invalid is_active value"}), 400

    query = {}
    if category_id is not None:
        query["category_id"] = category_id
    if business_id is not None:
        query["business_id"] = business_id
    if is_active is not None:
        query["is_active"] = is_active

    try:
        product_docs = list(products.find(query).sort("created_at", 1))
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    return jsonify({"products": [_serialize_product(product) for product in product_docs]}), 200




@products_bp.route("/<product_id>", methods=["PUT"])
def update_product(product_id: str):
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    if not ObjectId.is_valid(product_id):
        return jsonify({"error": "Invalid product id"}), 400

    data = _get_payload()
    image_file = request.files.get("image")
    update_doc = {}

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Invalid name"}), 400
        update_doc["name"] = name

    if "description" in data:
        update_doc["description"] = (data.get("description") or "").strip()

    if "category_id" in data:
        category_id = data.get("category_id")
        if not ObjectId.is_valid(category_id):
            return jsonify({"error": "Invalid category id"}), 400
        update_doc["category_id"] = ObjectId(category_id)

    if "price" in data:
        price = _parse_price(data.get("price"))
        if price is None:
            return jsonify({"error": "Invalid price"}), 400
        update_doc["price"] = price

    if "is_active" in data:
        is_active = _parse_bool(data.get("is_active"))
        if is_active is None:
            return jsonify({"error": "Invalid is_active value"}), 400
        update_doc["is_active"] = is_active

    if not update_doc and not image_file:
        return jsonify({"error": "No changes provided"}), 400

    mongo_id = ObjectId(product_id)
    try:
        product_doc = products.find_one({"_id": mongo_id, "business_id": business_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not product_doc:
        return jsonify({"error": "Product not found"}), 404

    old_image_path = product_doc.get("image_path")
    new_image_path = None
    if image_file and image_file.filename:
        try:
            new_image_path = _save_image(product_id, image_file)
        except OSError:
            return jsonify({"error": "File storage error occurred"}), 500
        update_doc["image_path"] = new_image_path

    try:
        if update_doc:
            products.update_one({"_id": mongo_id, "business_id": business_id}, {"$set": update_doc})
        product_doc = products.find_one({"_id": mongo_id, "business_id": business_id})
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if new_image_path and old_image_path and new_image_path != old_image_path:
        _delete_image(old_image_path)

    return jsonify({"product": _serialize_product(product_doc)}), 200


@products_bp.route("/<product_id>", methods=["DELETE"])
def delete_product(product_id: str):
    auth_error, business_id = _require_business()
    if auth_error:
        return auth_error

    if not ObjectId.is_valid(product_id):
        return jsonify({"error": "Invalid product id"}), 400

    try:
        deleted = delete_product_entry(product_id, business_id)
    except PyMongoError:
        return jsonify({"error": "Database error occurred"}), 500

    if not deleted:
        return jsonify({"error": "Product not found"}), 404

    return jsonify({"message": "Product deleted"}), 200

