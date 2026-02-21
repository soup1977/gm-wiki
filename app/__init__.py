from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

# Create the database object here, but don't attach it to an app yet
db = SQLAlchemy()

# Create the migration engine — this replaces db.create_all()
# Instead of recreating tables from scratch, Migrate tracks changes
# and applies them incrementally (like Git for your database schema)
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Attach the database and migration engine to this app instance
    db.init_app(app)
    migrate.init_app(app, db)

    # Register Blueprints — each Blueprint is a group of related routes
    from app.routes.main import main_bp
    from app.routes.campaigns import campaigns_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(campaigns_bp)

    return app