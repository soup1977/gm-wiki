from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
import markdown as _md
import os
import uuid

# Create the database object here, but don't attach it to an app yet
db = SQLAlchemy()

# Create the migration engine — this replaces db.create_all()
# Instead of recreating tables from scratch, Migrate tracks changes
# and applies them incrementally (like Git for your database schema)
migrate = Migrate()


def save_upload(file):
    """Save an uploaded image file to the uploads folder.

    Validates the file extension, generates a unique filename (UUID + original
    extension) to avoid collisions, then writes the file to UPLOAD_FOLDER.
    Returns the new filename string, or None if the file is missing/invalid.
    """
    from flask import current_app
    if not file or not file.filename:
        return None
    if '.' not in file.filename:
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in current_app.config.get('ALLOWED_EXTENSIONS', set()):
        return None
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
    return filename


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Attach the database and migration engine to this app instance
    db.init_app(app)
    migrate.init_app(app, db)

    # Ensure the uploads directory exists when the app starts
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register the 'md' Jinja2 filter — converts Markdown text to HTML
    # Usage in templates: {{ some_field | md | safe }}
    # The 'nl2br' extension turns single newlines into <br> tags
    @app.template_filter('md')
    def markdown_filter(text):
        if not text:
            return ''
        return _md.markdown(text, extensions=['nl2br'])

    # Register Blueprints — each Blueprint is a group of related routes
    from app.routes.main import main_bp
    from app.routes.campaigns import campaigns_bp
    from app.routes.locations import locations_bp
    from app.routes.npcs import npcs_bp
    from app.routes.quests import quests_bp
    from app.routes.items import items_bp
    from app.routes.compendium import compendium_bp
    from app.routes.sessions import sessions_bp
    from app.routes.tags import tags_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(npcs_bp)
    app.register_blueprint(quests_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(compendium_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(tags_bp)

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