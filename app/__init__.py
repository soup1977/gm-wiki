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
    from app.routes.locations import locations_bp
    from app.routes.npcs import npcs_bp
    from app.routes.quests import quests_bp
    from app.routes.items import items_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(npcs_bp)
    app.register_blueprint(quests_bp)
    app.register_blueprint(items_bp)

    # Context processor — makes active_campaign available in EVERY template
    # automatically, so we don't have to pass it in every route
    @app.context_processor
    def inject_active_campaign():
        from flask import session as flask_session
        from app.models import Campaign
        active_campaign_id = flask_session.get('active_campaign_id')
        active_campaign = Campaign.query.get(active_campaign_id) if active_campaign_id else None
        return dict(active_campaign=active_campaign)

    return app