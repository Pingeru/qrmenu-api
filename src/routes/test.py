from flask import Blueprint, jsonify
from src.utils.database_helper import db

test_bp = Blueprint("test", __name__)
businesses = db["businesses"]

@test_bp.route("/")
def test():
    businesses.count_documents({})
    return jsonify({"test": "succeed"})
