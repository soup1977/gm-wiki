from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
import markdown as _md
import os
import re
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
    # Supports standard Markdown plus Obsidian callouts and wiki-links
    @app.template_filter('md')
    def markdown_filter(text):
        if not text:
            return ''
        # Pre-process: convert Obsidian callouts to HTML before markdown parsing
        text = _convert_obsidian_callouts(text)
        # Pre-process: convert [[wiki-links]] to regular markdown links
        text = _convert_wiki_links(text)
        return _md.markdown(text, extensions=['nl2br', 'tables', 'fenced_code'])

    def _convert_obsidian_callouts(text):
        """Convert Obsidian callout syntax (> [!type] Title) to Bootstrap alerts.

        Obsidian callouts look like:
            > [!tip] Some Title
            > Body text here
            > More body text

        We convert these to HTML div blocks with Bootstrap alert classes.
        """
        # Map callout types to Bootstrap alert classes
        callout_map = {
            'tip': ('alert-success', 'bi-lightbulb'),
            'warning': ('alert-warning', 'bi-exclamation-triangle'),
            'important': ('alert-danger', 'bi-exclamation-circle'),
            'danger': ('alert-danger', 'bi-exclamation-circle'),
            'quote': ('alert-secondary', 'bi-quote'),
            'read-aloud': ('alert-info fst-italic', 'bi-megaphone'),
            'abstract': ('alert-secondary', 'bi-file-text'),
            'note': ('alert-primary', 'bi-info-circle'),
            'info': ('alert-info', 'bi-info-circle'),
            'example': ('alert-light', 'bi-journal-code'),
        }

        lines = text.split('\n')
        result = []
        in_callout = False
        callout_body = []
        callout_class = ''
        callout_icon = ''
        callout_title = ''

        for line in lines:
            # Check for callout start: > [!type] Optional Title
            match = re.match(r'^>\s*\[!(\w[\w-]*)\]\s*(.*)', line)
            if match and not in_callout:
                in_callout = True
                ctype = match.group(1).lower()
                callout_title = match.group(2).strip()
                callout_class, callout_icon = callout_map.get(
                    ctype, ('alert-secondary', 'bi-info-circle'))
                callout_body = []
                continue

            # Inside a callout: lines starting with > (or empty > lines)
            if in_callout:
                stripped = re.match(r'^>\s?(.*)', line)
                if stripped:
                    callout_body.append(stripped.group(1))
                    continue
                else:
                    # End of callout block — flush it
                    result.append(_render_callout(
                        callout_class, callout_icon, callout_title, callout_body))
                    in_callout = False
                    result.append(line)
                    continue

            result.append(line)

        # Flush any remaining callout at end of text
        if in_callout:
            result.append(_render_callout(
                callout_class, callout_icon, callout_title, callout_body))

        return '\n'.join(result)

    def _render_callout(cls, icon, title, body_lines):
        """Render a single callout block as a Bootstrap alert div."""
        body_html = _md.markdown('\n'.join(body_lines), extensions=['nl2br', 'tables'])
        title_html = f'<strong><i class="bi {icon}"></i> {title}</strong><br>' if title else ''
        return f'<div class="alert {cls}">{title_html}{body_html}</div>\n'

    def _convert_wiki_links(text):
        """Convert Obsidian [[wiki-links]] to bold text or search links.

        Handles two forms:
          [[Target]]           → **Target**
          [[Target|Display]]   → **Display**

        During import, these get resolved to actual GM Wiki URLs.
        At render time, unresolved links show as bold text so they're
        still readable even without a direct link target.
        """
        def replace_link(match):
            inner = match.group(1)
            if '|' in inner:
                _target, display = inner.split('|', 1)
                return f'**{display.strip()}**'
            return f'**{inner.strip()}**'

        return re.sub(r'\[\[([^\]]+)\]\]', replace_link, text)

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
    from app.routes.pcs import pcs_bp
    from app.routes.combat import combat_bp
    from app.routes.tables import tables_bp
    from app.routes.session_mode import session_mode_bp
    from app.routes.bestiary import bestiary_bp
    from app.routes.bestiary_import import bestiary_import_bp
    from app.routes.monsters import monsters_bp
    from app.routes.wiki import wiki_bp
    from app.routes.settings import settings_bp
    from app.routes.ai import ai_bp
    from app.routes.obsidian_import import obsidian_import_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(npcs_bp)
    app.register_blueprint(pcs_bp)
    app.register_blueprint(quests_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(compendium_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(combat_bp)
    app.register_blueprint(tables_bp)
    app.register_blueprint(session_mode_bp)
    app.register_blueprint(bestiary_bp)
    app.register_blueprint(bestiary_import_bp)
    app.register_blueprint(monsters_bp)
    app.register_blueprint(wiki_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(obsidian_import_bp)

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