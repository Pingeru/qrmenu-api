import os

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

API_PORT = int(os.getenv("API_PORT", 3005))

from src.routes.business_auth import business_auth_bp
from src.routes.client_auth import client_auth_bp

app.register_blueprint(business_auth_bp, url_prefix="/api/v1/business/auth")
app.register_blueprint(client_auth_bp, url_prefix="/api/v1/client/auth")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=API_PORT)