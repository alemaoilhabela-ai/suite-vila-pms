import os
from datetime import timedelta
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-mude")
    app.permanent_session_lifetime = timedelta(days=30)

    from app.routes import bp
    from app.auth import auth_bp
    app.register_blueprint(bp)
    app.register_blueprint(auth_bp)

    return app
