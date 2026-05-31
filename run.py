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
from src.routes.categories import categories_bp
from src.routes.products import products_bp
from src.routes.client_orders import client_orders_bp
from src.routes.business_orders import business_orders_bp
from src.routes.business_analytics import business_analytics_bp
from src.cron.scheduler import start_scheduler

app.register_blueprint(business_auth_bp, url_prefix="/api/v1/business/auth")
app.register_blueprint(client_auth_bp, url_prefix="/api/v1/client/auth")
app.register_blueprint(categories_bp, url_prefix="/api/v1/business/categories")
app.register_blueprint(products_bp, url_prefix="/api/v1/business/products")
app.register_blueprint(client_orders_bp, url_prefix="/api/v1/client/orders")
app.register_blueprint(business_orders_bp, url_prefix="/api/v1/business/orders")
app.register_blueprint(business_analytics_bp, url_prefix="/api/v1/business/analytics")

if __name__ == "__main__":
    start_scheduler(app)
    app.run(debug=True, host="0.0.0.0", port=API_PORT)