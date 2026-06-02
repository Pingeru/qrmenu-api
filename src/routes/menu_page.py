from flask import Blueprint, current_app, send_from_directory

menu_page_bp = Blueprint("menu_page", __name__)


@menu_page_bp.route("/<business_id>", methods=["GET"])
def get_menu_page(business_id):
    return send_from_directory(current_app.static_folder, "menu.html")

