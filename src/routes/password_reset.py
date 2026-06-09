from bson import ObjectId
from flask import Blueprint, render_template, request
from pymongo.errors import PyMongoError
import jwt

from src.utils.auth_helper import hash_password
from src.utils.database_helper import db
from src.utils.password_reset_helper import (
    decode_password_reset_token,
    get_account_display_name,
)

password_reset_bp = Blueprint("password_reset", __name__)

businesses = db["businesses"]
users = db["users"]


def _get_account_collection(account_type: str):
    if account_type == "business":
        return businesses
    if account_type == "client":
        return users
    return None


def _render_reset_page(
    *,
    token: str = "",
    token_valid: bool = False,
    account_type: str | None = None,
    recipient_name: str | None = None,
    error_message: str | None = None,
    success_message: str | None = None,
    status_code: int = 200,
):
    return (
        render_template(
            "password_reset.html",
            token=token,
            token_valid=token_valid,
            account_type=account_type,
            recipient_name=recipient_name,
            error_message=error_message,
            success_message=success_message,
        ),
        status_code,
    )


def _load_reset_context(token: str):
    payload = decode_password_reset_token(token)
    account_type = payload["account_type"]
    collection = _get_account_collection(account_type)
    if collection is None:
        raise jwt.InvalidTokenError("Invalid token payload")

    subject_id = payload.get("sub")
    mongo_id = ObjectId(subject_id) if ObjectId.is_valid(subject_id) else subject_id
    try:
        account_doc = collection.find_one({"_id": mongo_id})
    except PyMongoError:
        raise

    if not account_doc:
        raise LookupError("Account not found")

    return payload, account_doc, account_type


@password_reset_bp.route("/password-reset", methods=["GET"])
def password_reset_form():
    token = (request.args.get("token") or "").strip()
    if not token:
        return _render_reset_page(error_message="Missing reset token", status_code=400)

    try:
        _, account_doc, account_type = _load_reset_context(token)
    except jwt.ExpiredSignatureError:
        return _render_reset_page(error_message="This reset link has expired", status_code=401)
    except jwt.InvalidTokenError:
        return _render_reset_page(error_message="Invalid reset token", status_code=400)
    except PyMongoError:
        return _render_reset_page(error_message="Database error occurred", status_code=500)
    except LookupError:
        return _render_reset_page(error_message="Account not found", status_code=404)

    recipient_name = get_account_display_name(account_doc, account_type)
    return _render_reset_page(
        token=token,
        token_valid=True,
        account_type=account_type,
        recipient_name=recipient_name,
        status_code=200,
    )


@password_reset_bp.route("/password-reset", methods=["POST"])
def password_reset_submit():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    token = (data.get("token") or request.args.get("token") or "").strip()
    new_password = data.get("password") or data.get("new_password") or ""
    confirm_password = data.get("confirm_password") or data.get("password_confirm") or ""

    if not token or not new_password or not confirm_password:
        return _render_reset_page(
            token=token,
            error_message="Missing required fields",
            status_code=400,
        )

    if new_password != confirm_password:
        return _render_reset_page(
            token=token,
            error_message="Passwords do not match",
            status_code=400,
        )

    try:
        _, account_doc, account_type = _load_reset_context(token)
    except jwt.ExpiredSignatureError:
        return _render_reset_page(token=token, error_message="This reset link has expired", status_code=401)
    except jwt.InvalidTokenError:
        return _render_reset_page(token=token, error_message="Invalid reset token", status_code=400)
    except PyMongoError:
        return _render_reset_page(token=token, error_message="Database error occurred", status_code=500)
    except LookupError:
        return _render_reset_page(token=token, error_message="Account not found", status_code=404)

    recipient_name = get_account_display_name(account_doc, account_type)
    collection = _get_account_collection(account_type)
    mongo_id = ObjectId(account_doc["_id"]) if ObjectId.is_valid(str(account_doc["_id"])) else account_doc["_id"]

    try:
        update_result = collection.update_one(
            {"_id": mongo_id},
            {"$set": {"password_hash": hash_password(new_password)}},
        )
    except PyMongoError:
        return _render_reset_page(token=token, error_message="Database error occurred", status_code=500)

    if update_result.matched_count == 0:
        return _render_reset_page(token=token, error_message="Account not found", status_code=404)

    return _render_reset_page(
        token="",
        token_valid=False,
        account_type=account_type,
        recipient_name=recipient_name,
        success_message="Password has been reset successfully",
        status_code=200,
    )

