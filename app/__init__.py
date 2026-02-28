from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
import markdown as _md
import os
import re
import uuid

# App version — bump this on each release. Appended to static file URLs
# as a cache-busting query string so browsers/Cloudflare pick up changes.
APP_VERSION = '1.1.0'

# Create the database object here, but don't attach it to an app yet
db = SQLAlchemy()

# Create the migration engine — this replaces db.create_all()
# Instead of recreating tables from scratch, Migrate tracks changes
# and applies them incrementally (like Git for your database schema)
migrate = Migrate()

# Login manager — handles session-based user authentication
login_manager = LoginManager()

# CSRF protection — prevents cross-site request forgery attacks.
# Every POST form must include {{ csrf_token() }} as a hidden input.
csrf = CSRFProtect()

# Rate limiter — prevents brute-force attacks on login/signup.
# Uses in-memory storage by default (sufficient for single-server deployment).
limiter = Limiter(key_func=get_remote_address, default_limits=[])


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

    # Set up Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

    # Set up CSRF protection
    csrf.init_app(app)

    # Set up rate limiting
    limiter.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

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
    from app.routes.auth import auth_bp
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
    from app.routes.entity_search import entity_search_bp
    from app.routes.encounters import encounters_bp
    from app.routes.factions import factions_bp
    from app.routes.quick_create import quick_create_bp
    from app.routes.admin import admin_bp
    from app.routes.global_search import global_search_bp
    from app.routes.srd_import import srd_import_bp
    from app.routes.sd_generate import sd_generate_bp

    app.register_blueprint(auth_bp)
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
    app.register_blueprint(entity_search_bp)
    app.register_blueprint(encounters_bp)
    app.register_blueprint(factions_bp)
    app.register_blueprint(quick_create_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(global_search_bp)
    app.register_blueprint(srd_import_bp)
    app.register_blueprint(sd_generate_bp)

    # Exempt AJAX-only blueprints from CSRF — these are called from JavaScript
    # using fetch() and are already protected by same-origin policy + login_required
    csrf.exempt(ai_bp)
    csrf.exempt(quick_create_bp)
    csrf.exempt(sd_generate_bp)

    # Context processor — makes active_campaign and ai_enabled available
    # in EVERY template automatically, so we don't have to pass them in every route
    @app.context_processor
    def inject_active_campaign():
        from flask import session as flask_session
        from flask_login import current_user
        from app.models import Campaign
        active_campaign_id = flask_session.get('active_campaign_id')
        active_campaign = None
        if active_campaign_id:
            active_campaign = Campaign.query.get(active_campaign_id)
            # Clear stale session if campaign belongs to a different user
            if active_campaign and current_user.is_authenticated:
                if active_campaign.user_id and active_campaign.user_id != current_user.id:
                    flask_session.pop('active_campaign_id', None)
                    active_campaign = None
        return dict(active_campaign=active_campaign)

    @app.context_processor
    def inject_app_version():
        return dict(app_version=APP_VERSION)

    @app.context_processor
    def override_url_for():
        """Append version query string to static file URLs for cache busting."""
        def versioned_url_for(endpoint, **values):
            from flask import url_for as _url_for
            if endpoint == 'static':
                values['v'] = APP_VERSION
            return _url_for(endpoint, **values)
        return dict(url_for=versioned_url_for)

    @app.context_processor
    def inject_ai_status():
        from app.ai_provider import is_ai_enabled
        from app.sd_provider import is_sd_enabled
        try:
            return dict(ai_enabled=is_ai_enabled(), sd_enabled=is_sd_enabled())
        except Exception:
            return dict(ai_enabled=False, sd_enabled=False)

    # CLI command: flask seed-icrpg
    # Loads ICRPG bestiary entries from the bundled JSON seed data.
    # Bestiary entries are global (no campaign_id), so this only needs to run once.
    @app.cli.command('seed-icrpg')
    def seed_icrpg():
        """Load ICRPG bestiary seed data into the database."""
        import json as _json
        from app.models import BestiaryEntry

        seed_path = os.path.join(app.root_path, 'seed_data', 'icrpg_bestiary.json')
        with open(seed_path) as f:
            entries = _json.load(f)

        imported = 0
        skipped = 0
        for entry in entries:
            name = entry['name']
            if BestiaryEntry.query.filter_by(name=name, system='ICRPG').first():
                skipped += 1
                continue
            be = BestiaryEntry(
                name=name,
                system=entry.get('system', 'ICRPG'),
                stat_block=entry.get('stat_block', ''),
                cr_level=entry.get('cr_level', ''),
                source=entry.get('source', 'ICRPG Master Edition'),
                tags=entry.get('tags', ''),
            )
            db.session.add(be)
            imported += 1

        db.session.commit()
        print(f'Imported {imported} ICRPG bestiary entries. Skipped {skipped} duplicates.')

    return app