from io import BytesIO

import qrcode, os
from flask import Blueprint, jsonify, send_file

from src.middleware.auth_middleware import authenticate_request

business_qr_bp = Blueprint("business_qr", __name__)
MENU_URL = os.getenv("MENU_URL", "https://qrmenu.dovanay.com/menu")

@business_qr_bp.route("/", methods=["GET"])
def get_business_qr():
    auth_result = authenticate_request()
    if isinstance(auth_result, tuple):
        return auth_result

    if auth_result.get("user_type") != "business":
        return jsonify({"error": "Access forbidden"}), 403

    business_id = auth_result.get("_id")
    qr_url = f"{MENU_URL}/{business_id}"

    qr_img = qrcode.make(qr_url)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="image/png",
        as_attachment=True,
        download_name="menu-qr.png",
        max_age=0,
    )

