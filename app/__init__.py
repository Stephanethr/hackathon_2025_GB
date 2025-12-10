from flask import Flask
from app.config import DevelopmentConfig
from app.extensions import db, migrate

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    
    # Register Blueprints
    from app.api.routes.auth import auth_bp
    from app.api.routes.bookings import bookings_bp
    from app.api.routes.chat import chat_bp
    from app.api.routes.main import main_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(bookings_bp, url_prefix='/api/bookings')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(main_bp)

    def health():
        return {"status": "ok", "app": "WorkspaceSmart"}

    return app
