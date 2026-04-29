import os

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

API_PORT = int(os.getenv("API_PORT", 3005))

from src.routes.test import test_bp
from src.routes.menu import menu_bp
app.register_blueprint(test_bp, url_prefix="/api/v1/test")
app.register_blueprint(menu_bp, url_prefix="/api/v1/menu")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=API_PORT)