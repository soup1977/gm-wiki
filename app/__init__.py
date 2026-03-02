from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
import bleach
import markdown as _md
import os
import re
import uuid

# Tags and attributes allowed after Markdown rendering.
# Strips dangerous tags like <script> while preserving formatting.
ALLOWED_TAGS = {
    'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'pre', 'code', 'hr', 'img', 'div', 'span',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
    'strong', 'em', 'b', 'i', 'a', 'blockquote',
    'sub', 'sup', 'abbr',
}
ALLOWED_ATTRS = {
    'img': ['src', 'alt', 'title', 'class'],
    'a': ['href', 'title', 'class'],
    'div': ['class'],
    'span': ['class'],
    'i': ['class'],
    'th': ['class'],
    'td': ['class'],
    'table': ['class'],
    'code': ['class'],
    'abbr': ['title'],
}

# App version — bump this on each release. Appended to static file URLs
# as a cache-busting query string so browsers/Cloudflare pick up changes.
APP_VERSION = '1.2.0'

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
    # Validate actual file content matches an image format (not just extension)
    import imghdr  # deprecated in 3.11, removed in 3.13 — sufficient for now
    header = file.read(512)
    file.seek(0)
    detected = imghdr.what(None, h=header)
    if detected not in ('png', 'jpeg', 'gif', 'webp', 'rgb'):
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
        html = _md.markdown(text, extensions=['nl2br', 'tables', 'fenced_code'])
        return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)

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
        body_html = bleach.clean(body_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)
        safe_title = bleach.clean(title) if title else ''
        title_html = f'<strong><i class="bi {icon}"></i> {safe_title}</strong><br>' if safe_title else ''
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
    from app.routes.adventure_sites import adventure_sites_bp
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
    from app.routes.campaign_assistant import campaign_assistant_bp
    from app.routes.icrpg_catalog import icrpg_catalog_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(npcs_bp)
    app.register_blueprint(pcs_bp)
    app.register_blueprint(quests_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(compendium_bp)
    app.register_blueprint(adventure_sites_bp)
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
    app.register_blueprint(campaign_assistant_bp)
    app.register_blueprint(icrpg_catalog_bp)

    # Exempt AJAX-only blueprints from CSRF — these are called from JavaScript
    # using fetch() and are already protected by same-origin policy + login_required
    csrf.exempt(ai_bp)
    csrf.exempt(quick_create_bp)
    csrf.exempt(sd_generate_bp)
    csrf.exempt(campaign_assistant_bp)

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
            if current_user.is_authenticated:
                active_campaign = Campaign.query.filter_by(
                    id=active_campaign_id, user_id=current_user.id
                ).first()
                if not active_campaign:
                    flask_session.pop('active_campaign_id', None)
            else:
                flask_session.pop('active_campaign_id', None)
        is_icrpg = ('icrpg' in (active_campaign.system or '').lower()) if active_campaign else False
        return dict(active_campaign=active_campaign, is_icrpg=is_icrpg)

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

    # -----------------------------------------------------------------
    # CLI: flask seed-icrpg
    # Loads ICRPG bestiary + monster entries (global, no campaign_id).
    # -----------------------------------------------------------------
    @app.cli.command('seed-icrpg')
    def seed_icrpg():
        """Load ICRPG bestiary and monster seed data into the database."""
        import json as _json
        from app.models import BestiaryEntry

        imported = 0
        skipped = 0

        for filename in ('icrpg_bestiary.json', 'icrpg_monsters.json'):
            seed_path = os.path.join(app.root_path, 'seed_data', filename)
            if not os.path.exists(seed_path):
                print(f'  Skipping {filename} (not found)')
                continue
            with open(seed_path) as f:
                entries = _json.load(f)
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

    # -----------------------------------------------------------------
    # CLI: flask seed-icrpg-catalog
    # Loads ICRPG catalog data: worlds, life forms, types, abilities,
    # loot definitions, spells, and milestone paths.
    # -----------------------------------------------------------------
    @app.cli.command('seed-icrpg-catalog')
    def seed_icrpg_catalog():
        """Load ICRPG catalog seed data (worlds, life forms, types, abilities, loot, spells, paths)."""
        import json as _json
        from app.models import (ICRPGWorld, ICRPGLifeForm, ICRPGType,
                                ICRPGAbility, ICRPGLootDef, ICRPGStartingLoot,
                                ICRPGSpell, ICRPGMilestonePath)

        seed_dir = os.path.join(app.root_path, 'seed_data')
        stats = {'worlds': 0, 'life_forms': 0, 'types': 0,
                 'abilities': 0, 'loot_defs': 0, 'starting_loot': 0,
                 'spells': 0, 'paths': 0, 'skipped': 0}

        # ── 1. Worlds ──────────────────────────────────────────────
        path = os.path.join(seed_dir, 'icrpg_worlds.json')
        with open(path) as f:
            worlds_data = _json.load(f)
        world_map = {}  # name → ICRPGWorld instance
        for w in worlds_data:
            existing = ICRPGWorld.query.filter_by(name=w['name'], is_builtin=True).first()
            if existing:
                world_map[w['name']] = existing
                stats['skipped'] += 1
                continue
            obj = ICRPGWorld(name=w['name'], description=w.get('description', ''),
                            is_builtin=True)
            db.session.add(obj)
            db.session.flush()  # get the id
            world_map[w['name']] = obj
            stats['worlds'] += 1
        print(f"  Worlds: {stats['worlds']} imported")

        # ── 2. Life Forms ──────────────────────────────────────────
        path = os.path.join(seed_dir, 'icrpg_life_forms.json')
        with open(path) as f:
            lf_data = _json.load(f)
        for lf in lf_data:
            world = world_map.get(lf['world'])
            if not world:
                print(f"  WARNING: World '{lf['world']}' not found for life form '{lf['name']}'")
                continue
            existing = ICRPGLifeForm.query.filter_by(
                name=lf['name'], world_id=world.id, is_builtin=True).first()
            if existing:
                stats['skipped'] += 1
                continue
            obj = ICRPGLifeForm(
                world_id=world.id, name=lf['name'],
                description=lf.get('description', ''),
                bonuses=lf.get('bonuses'), is_builtin=True)
            db.session.add(obj)
            stats['life_forms'] += 1
        print(f"  Life Forms: {stats['life_forms']} imported")

        # ── 3. Types + Abilities + Starting Loot ───────────────────
        path = os.path.join(seed_dir, 'icrpg_types.json')
        with open(path) as f:
            types_data = _json.load(f)
        for t in types_data:
            world = world_map.get(t['world'])
            if not world:
                print(f"  WARNING: World '{t['world']}' not found for type '{t['name']}'")
                continue
            existing = ICRPGType.query.filter_by(
                name=t['name'], world_id=world.id, is_builtin=True).first()
            if existing:
                stats['skipped'] += 1
                continue
            type_obj = ICRPGType(
                world_id=world.id, name=t['name'],
                description=t.get('description', ''), is_builtin=True)
            db.session.add(type_obj)
            db.session.flush()  # get the id

            # Starting abilities
            for i, ab in enumerate(t.get('starting_abilities', [])):
                db.session.add(ICRPGAbility(
                    type_id=type_obj.id, name=ab['name'],
                    description=ab.get('description', ''),
                    ability_kind='starting', is_builtin=True, display_order=i))
                stats['abilities'] += 1

            # Milestone abilities
            for i, ab in enumerate(t.get('milestone_abilities', [])):
                db.session.add(ICRPGAbility(
                    type_id=type_obj.id, name=ab['name'],
                    description=ab.get('description', ''),
                    ability_kind='milestone', is_builtin=True, display_order=i))
                stats['abilities'] += 1

            # Mastery abilities
            for i, ab in enumerate(t.get('mastery_abilities', [])):
                db.session.add(ICRPGAbility(
                    type_id=type_obj.id, name=ab['name'],
                    description=ab.get('description', ''),
                    ability_kind='mastery', is_builtin=True, display_order=i))
                stats['abilities'] += 1

            # Starting loot (stored as ICRPGLootDef + ICRPGStartingLoot link)
            for sl in t.get('starting_loot', []):
                loot_def = ICRPGLootDef(
                    world_id=world.id, name=sl['name'],
                    loot_type=sl.get('loot_type', 'Item'),
                    description=sl.get('description', ''),
                    is_starter=True, is_builtin=True,
                    source='ICRPG Master Edition')
                db.session.add(loot_def)
                db.session.flush()
                db.session.add(ICRPGStartingLoot(
                    type_id=type_obj.id, loot_def_id=loot_def.id))
                stats['loot_defs'] += 1
                stats['starting_loot'] += 1

            stats['types'] += 1
        print(f"  Types: {stats['types']} imported")
        print(f"  Abilities: {stats['abilities']} imported")
        print(f"  Starting Loot Defs: {stats['loot_defs']} imported")
        print(f"  Starting Loot Links: {stats['starting_loot']} imported")

        # ── 4. Starter Loot (basic loot tables per world) ──────────
        path = os.path.join(seed_dir, 'icrpg_starter_loot.json')
        basic_loot_count = 0
        if os.path.exists(path):
            with open(path) as f:
                loot_tables = _json.load(f)
            for table in loot_tables:
                world = world_map.get(table.get('setting'))
                for entry in table.get('entries', []):
                    existing = ICRPGLootDef.query.filter_by(
                        name=entry['name'], is_builtin=True).first()
                    if existing:
                        # Update effects/slot_cost on re-seed
                        if 'effects' in entry:
                            existing.effects = entry['effects']
                        if 'slot_cost' in entry:
                            existing.slot_cost = entry['slot_cost']
                        stats['skipped'] += 1
                        continue
                    obj = ICRPGLootDef(
                        world_id=world.id if world else None,
                        name=entry['name'],
                        loot_type=entry.get('type', 'Item'),
                        description=entry.get('description', ''),
                        effects=entry.get('effects'),
                        slot_cost=entry.get('slot_cost', 1),
                        is_starter=True, is_builtin=True,
                        source='ICRPG Master Edition')
                    db.session.add(obj)
                    basic_loot_count += 1
        print(f"  Basic Loot Defs: {basic_loot_count} imported")

        # ── 5. Spells ──────────────────────────────────────────────
        path = os.path.join(seed_dir, 'icrpg_spells.json')
        spell_count = 0
        if os.path.exists(path):
            with open(path) as f:
                spells_data = _json.load(f)
            for sp in spells_data:
                # Derive casting_stat from spell type
                stype = (sp.get('type') or '').lower()
                casting_stat = 'INT' if stype == 'arcane' else ('WIS' if stype in ('holy', 'infernal') else None)

                existing = ICRPGSpell.query.filter_by(
                    name=sp['name'], is_builtin=True).first()
                if existing:
                    # Update casting_stat on re-seed
                    if casting_stat and not existing.casting_stat:
                        existing.casting_stat = casting_stat
                    stats['skipped'] += 1
                    continue
                obj = ICRPGSpell(
                    name=sp['name'],
                    spell_type=sp.get('type'),
                    casting_stat=casting_stat,
                    level=sp.get('level', 1),
                    target=sp.get('target'),
                    duration=sp.get('duration'),
                    description=sp.get('description', ''),
                    is_builtin=True,
                    source=sp.get('source', 'ICRPG Master Edition'))
                db.session.add(obj)
                spell_count += 1
        print(f"  Spells: {spell_count} imported")

        # ── 6. Milestone Paths ─────────────────────────────────────
        path = os.path.join(seed_dir, 'icrpg_milestone_paths.json')
        path_count = 0
        if os.path.exists(path):
            with open(path) as f:
                paths_data = _json.load(f)
            for mp in paths_data:
                existing = ICRPGMilestonePath.query.filter_by(
                    name=mp['name'], is_builtin=True).first()
                if existing:
                    stats['skipped'] += 1
                    continue
                obj = ICRPGMilestonePath(
                    name=mp['name'],
                    description=mp.get('description', ''),
                    tiers=mp.get('tiers'),
                    is_builtin=True)
                db.session.add(obj)
                path_count += 1
        print(f"  Milestone Paths: {path_count} imported")

        db.session.commit()
        print(f"\nDone! Skipped {stats['skipped']} duplicates.")

    # Security headers — added to every response
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "frame-ancestors 'self'"
        )
        if request.headers.get('X-Forwarded-Proto') == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    return app