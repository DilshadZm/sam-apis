from flask import Flask
from app.database import init_db
from app.equipment_routes import equipment_bp
from app.location_routes import location_bp
from app.auth_routes import auth_bp

def create_app():
    app = Flask(__name__)

    init_db()

    app.register_blueprint(equipment_bp)
    app.register_blueprint(location_bp)
    app.register_blueprint(auth_bp)

    return app