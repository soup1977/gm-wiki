# GM Wiki — Phase 6: Player Wiki View & Docker Deployment

## Overview

Phase 6 delivers two things:
1. **Player Wiki View** — A read-only, player-facing view of campaign content (no GM secrets)
2. **Docker Packaging & Unraid Deployment** — Containerize the app for reliable self-hosting

After this phase, GM Wiki is fully production-ready: players can pull up the wiki on a tablet during a session, and the whole app runs as a Docker container on your Unraid server.

---

## What's Already Done (Good News)

The groundwork for Phase 6 was laid throughout earlier phases. These flags already exist in the models:

| Model            | Flag                      | Meaning                          |
|------------------|---------------------------|----------------------------------|
| NPC              | `is_player_visible`       | Show this NPC in the player wiki |
| Location         | `is_player_visible`       | Show this location               |
| Quest            | `is_player_visible`       | Show this quest                  |
| Item             | `is_player_visible`       | Show this item                   |
| Session          | `is_player_visible`       | Show this session recap          |
| BestiaryEntry    | `visible_to_players`      | Show this creature (name/image/tags only — NO stat block) |
| CompendiumEntry  | `is_gm_only`              | Hide this entry if True          |

Phase 6 just needs to *use* these flags by building the player-facing routes and templates.

---

## Part 1: Player Wiki View

### Design Principles

- **Read-only** — No create/edit/delete buttons, no forms
- **GM secrets never leak** — `secrets`, `gm_notes`, stat blocks (bestiary), and any `is_gm_only` content are never rendered
- **Campaign-scoped** — Each campaign has its own wiki
- **No login required** — This is a local network tool; authentication is out of scope
- **Tablet-friendly** — Clean layout, readable font, minimal clutter

### URL Structure

All player wiki routes live under `/wiki/`:

| Route                              | Purpose                                 |
|------------------------------------|-----------------------------------------|
| `/wiki/`                           | List all campaigns (wiki landing page)  |
| `/wiki/<campaign_id>/`             | Campaign wiki home                      |
| `/wiki/<campaign_id>/npcs`         | NPC list (visible only)                 |
| `/wiki/<campaign_id>/npcs/<id>`    | NPC detail (no secrets/gm_notes)        |
| `/wiki/<campaign_id>/locations`    | Location list (visible only)            |
| `/wiki/<campaign_id>/locations/<id>` | Location detail (no gm_notes)         |
| `/wiki/<campaign_id>/quests`       | Quest list (visible only)               |
| `/wiki/<campaign_id>/quests/<id>`  | Quest detail (no gm_notes)              |
| `/wiki/<campaign_id>/items`        | Item list (visible only)                |
| `/wiki/<campaign_id>/items/<id>`   | Item detail (no gm_notes)               |
| `/wiki/<campaign_id>/sessions`     | Session recap list (visible only)       |
| `/wiki/<campaign_id>/sessions/<id>` | Session detail (summary only, no gm_notes) |
| `/wiki/<campaign_id>/compendium`   | Compendium entries (where is_gm_only=False) |
| `/wiki/<campaign_id>/bestiary`     | Bestiary (where visible_to_players=True) |
| `/wiki/<campaign_id>/bestiary/<id>` | Creature detail (name, image, tags, source — NO stat block) |

### Player Wiki Blueprint

New file: `app/routes/wiki.py`

This is a new Blueprint registered at the `/wiki` prefix. It's entirely separate from the GM routes — no shared logic, no risk of accidentally exposing GM data.

**Key filtering rules per entity:**

**NPCs**
- Query: `NPC.query.filter_by(campaign_id=..., is_player_visible=True)`
- Show: name, role, status, faction, physical_description, personality, portrait
- Hide: `secrets`, `notes` (GM notes field)

**Locations**
- Query: `Location.query.filter_by(campaign_id=..., is_player_visible=True)`
- Show: name, type, description, map image, connected locations (if also visible), child locations (if also visible)
- Hide: `gm_notes`

**Quests**
- Query: `Quest.query.filter_by(campaign_id=..., is_player_visible=True)`
- Show: name, status, hook, description, outcome (once completed — this is player-shareable), involved NPCs/locations (link only if also visible)
- Hide: `gm_notes`

**Items**
- Query: `Item.query.filter_by(campaign_id=..., is_player_visible=True)`
- Show: name, type, rarity, description, origin location (link if visible)
- Hide: `gm_notes`

**Sessions**
- Query: `Session.query.filter_by(campaign_id=..., is_player_visible=True)`
- Show: number, title, date_played, summary
- Hide: `gm_notes`

**Compendium**
- Query: `CompendiumEntry.query.filter_by(campaign_id=..., is_gm_only=False)`
- Show: title, category, content (Markdown rendered)
- No toggle to show hidden entries

**Bestiary**
- Query: `BestiaryEntry.query.filter_by(visible_to_players=True)`
- Show: name, image, tags, source
- Hide: stat_block, cr_level, system — these are NEVER shown to players

### Player Wiki Layout (base_wiki.html)

A separate base template for the wiki that:
- Has a simpler, cleaner navbar (no GM tools)
- Shows campaign name in header
- Has "GM Wiki" branding so players know what app this is
- Does NOT include: Session Mode, Combat Tracker, Campaigns, Tables, Bestiary (GM), Tags
- Has a "Back to GM View" link (for the GM's own tablet)

The wiki navbar shows:
- NPCs | Locations | Quests | Items | Sessions | Compendium | Bestiary

### Campaign Wiki Home Page (`/wiki/<campaign_id>/`)

At-a-glance view for players:
- Campaign name and system
- Current session number (most recent visible session, summary preview)
- Active quests (visible + status="active")
- Quick links to all sections
- Recent NPCs added/updated

### What Happens When Nothing Is Visible?

If a section has no visible entries yet, show an empty state:
- "No NPCs have been revealed yet."
- "No quests are visible yet."
- Etc.

This is intentional — the GM controls what players see by toggling the visibility flag.

---

## Part 2: Docker Packaging

### Why Docker?

Right now the app runs with `python3 run.py` using your system Python. Docker packages everything (Python, Flask, all dependencies) into a single container that runs reliably anywhere, including Unraid.

**What Docker adds:**
- Consistent Python version (no "it works on my Mac but not on Unraid")
- Easy start/stop via Unraid UI
- Automatic restart if the app crashes
- Clean separation from host system

### Files to Create

#### `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy and install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create upload directory
RUN mkdir -p /app/app/static/uploads

# Expose port
EXPOSE 5000

# Run with gunicorn (production WSGI server, not Flask dev server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "run:app"]
```

**Why gunicorn instead of `flask run`?**

Flask's built-in dev server is not safe for production — it handles only one request at a time and has debug features that shouldn't be on in production. Gunicorn is a proper WSGI server that handles multiple requests cleanly.

#### `docker-compose.yml`

For easy local development and Unraid deployment:

```yaml
version: '3.8'

services:
  gm-wiki:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./instance:/app/instance          # Database persists here
      - ./uploads:/app/app/static/uploads  # Uploaded images persist here
    environment:
      - SECRET_KEY=change-this-to-a-random-string
      - DATABASE_URL=sqlite:////app/instance/gm_wiki.db
      - FLASK_ENV=production
    restart: unless-stopped
```

**What the volumes do:**
- `./instance` → holds the SQLite database (`gm_wiki.db`). Without this, the database resets every time the container restarts.
- `./uploads` → holds portrait images, maps, etc. Without this, all uploaded images are lost on restart.

#### `.dockerignore`

```
__pycache__/
*.pyc
*.pyo
.env
instance/
*.db
.git/
.gitignore
phase-*.md
CLAUDE.md
README.md
```

This keeps the image small by excluding files Docker doesn't need.

### Config Changes Required

Currently `config.py` has hardcoded values. These need to come from environment variables so Docker can configure them without rebuilding the image.

**Update `config.py`:**

```python
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-only-insecure-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'gm_wiki.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB upload limit
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or \
        os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app', 'static', 'uploads')
```

**Key points:**
- `SECRET_KEY` — Must be set in production. If it changes, all browser sessions are invalidated (logged-out users).
- `DATABASE_URL` — Points to the mounted volume path inside the container.
- Falls back to safe defaults for local development (nothing breaks if you don't set env vars).

### Add gunicorn to requirements.txt

```
gunicorn>=21.0
```

### Migration on First Run (Docker)

When the container first starts, the database doesn't exist yet. We need `flask db upgrade` to run automatically.

**Update `run.py` or add a startup script:**

Option: Add a startup entrypoint script `docker-entrypoint.sh`:

```bash
#!/bin/bash
set -e

echo "Running database migrations..."
FLASK_APP=run.py python3 -m flask db upgrade

echo "Starting GM Wiki..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 run:app
```

Then in Dockerfile use `CMD ["/app/docker-entrypoint.sh"]` instead.

This means every time the container starts, migrations run first (safe to run multiple times — Alembic skips already-applied migrations).

---

## Part 3: Unraid Deployment

### What Unraid Needs

Unraid runs Docker containers. To add GM Wiki, you either:
1. Use the **Docker Compose Manager** plugin (if installed) — paste in the `docker-compose.yml`
2. Or configure manually via the **Unraid Docker UI**

### Manual Unraid Docker Setup

In the Unraid UI → Docker → Add Container:

| Field         | Value                                           |
|---------------|-------------------------------------------------|
| Name          | gm-wiki                                         |
| Repository    | (your Docker Hub username)/gm-wiki:latest       |
| Network Type  | Bridge                                          |
| Port Mapping  | Host: 5000 → Container: 5000                    |
| Volume 1      | Host: /mnt/user/appdata/gm-wiki/instance → Container: /app/instance |
| Volume 2      | Host: /mnt/user/appdata/gm-wiki/uploads → Container: /app/app/static/uploads |
| Env: SECRET_KEY | (random string you generate)                  |
| Env: DATABASE_URL | sqlite:////app/instance/gm_wiki.db          |
| Restart Policy | Unless Stopped                                 |

### Accessing the App

After deployment, access GM Wiki at:
- `http://YOUR_UNRAID_IP:5000` — GM view
- `http://YOUR_UNRAID_IP:5000/wiki/` — Player wiki

Players on your local network can browse to the wiki URL on their phones/tablets.

### Optional: Unraid Community Apps Template

A `.xml` template file that lets the app appear in the Unraid Community Apps store. Creates a polished install experience with a form. This is a nice-to-have, not required.

---

## Part 4: Build Sequence

### Step 1: Player Wiki Blueprint
**Branch:** `feature/player-wiki`

Tasks:
1. Create `app/routes/wiki.py` with the Blueprint
2. Register Blueprint in `app/__init__.py` at prefix `/wiki`
3. Create `app/templates/wiki/base_wiki.html` (player-facing base layout)
4. Create wiki index: `app/templates/wiki/index.html` (campaign landing)
5. Create wiki templates for each entity type (npcs, locations, quests, items, sessions, compendium, bestiary)
6. Verify GM-only fields are NOT present in any wiki template
7. Add "Player Wiki" link to GM sidebar on campaign pages (easy way for GM to share link)
8. Test: toggle `is_player_visible` on an NPC — confirm it appears/disappears in wiki

**Migration:** None needed — all flags already exist in models.

### Step 2: Docker Setup
**Branch:** `feature/docker`

Tasks:
1. Add `gunicorn` to `requirements.txt`
2. Update `config.py` to read from environment variables
3. Write `Dockerfile`
4. Write `docker-compose.yml`
5. Write `.dockerignore`
6. Write `docker-entrypoint.sh` (runs migrations then starts gunicorn)
7. Build image locally: `docker build -t gm-wiki .`
8. Run locally: `docker compose up`
9. Verify: app accessible at `http://localhost:5000`
10. Verify: database persists after `docker compose down && docker compose up`
11. Verify: uploaded images persist after restart
12. Update `README.md` with Docker deployment instructions

### Step 3: Unraid Deployment
**Branch:** `feature/docker` (continue) or a hotfix after Step 2 is merged

Tasks:
1. Push Docker image to Docker Hub (or use a private registry)
2. Configure container in Unraid Docker UI
3. Test access from another device on the local network
4. Confirm volumes are correctly mapped to `/mnt/user/appdata/gm-wiki/`
5. Test that data survives container restart

### Step 4: Polish & Cleanup
**Branch:** `feature/player-wiki` (or separate cleanup branch)

Tasks:
1. Add a "Share Player Wiki" button to Campaign detail page (copies URL to clipboard)
2. Review all existing entity forms — confirm the `is_player_visible` toggle is on every relevant create/edit form
3. Add a "Player Visibility" toggle to Compendium create/edit form if missing
4. Review Bestiary Entry form — confirm `visible_to_players` checkbox is prominent
5. Add a summary banner to Campaign detail page: "X of Y NPCs visible to players"
6. Final round of testing across all wiki routes

---

## Templates to Create

### `app/templates/wiki/base_wiki.html`
- Clean, read-only layout
- No GM toolbar, no edit buttons, no flash messages
- Campaign name in header
- Simple nav: NPCs | Locations | Quests | Items | Sessions | Compendium | Bestiary
- "GM View" link for the GM to jump back (subtle, bottom of page)

### `app/templates/wiki/index.html`
- Campaign home: name, description, active quests, recent sessions
- Cards linking to each section

### `app/templates/wiki/npcs/index.html`
- Card grid: portrait, name, role, status badge
- Filter by tag (if any visible tags)
- Search by name

### `app/templates/wiki/npcs/detail.html`
- Portrait (if uploaded)
- Name, role, status
- Faction (if set)
- Physical description (rendered Markdown)
- Personality (rendered Markdown)
- Associated locations (linked, only visible ones)
- Sessions appeared (linked, only visible ones)
- Tags

### `app/templates/wiki/locations/index.html`
- Card/list: name, type, description excerpt
- Hierarchical display (parent → children indented)

### `app/templates/wiki/locations/detail.html`
- Name, type
- Description (Markdown)
- Map image (if uploaded)
- Parent location link
- Child locations list
- Connected locations list
- NPCs here (linked, visible only)
- Quests involving this location (linked, visible only)

### `app/templates/wiki/quests/index.html`
- List: name, status badge, hook excerpt
- Filter by status

### `app/templates/wiki/quests/detail.html`
- Name, status badge
- Hook (Markdown)
- Description (Markdown)
- Outcome (Markdown, shown even when completed)
- Involved NPCs (visible only)
- Involved locations (visible only)
- Tags

### `app/templates/wiki/items/index.html`
- Table or cards: name, type, rarity badge

### `app/templates/wiki/items/detail.html`
- Name, type, rarity
- Description (Markdown)
- Owner NPC (if visible)
- Origin location (if visible)

### `app/templates/wiki/sessions/index.html`
- List: Session # | Title | Date | Summary excerpt
- Newest first

### `app/templates/wiki/sessions/detail.html`
- Session #, title, date
- Summary (Markdown)
- NPCs featured (visible only)
- Locations visited (visible only)

### `app/templates/wiki/compendium/index.html`
- List: title, category badge
- Filter by category

### `app/templates/wiki/compendium/detail.html`
- Title, category
- Content (Markdown)

### `app/templates/wiki/bestiary/index.html`
- Card gallery: name, image thumbnail, tags
- Filter by tag
- Search by name

### `app/templates/wiki/bestiary/detail.html`
- Name
- Image
- Tags
- Source
- **Nothing else** — no stat block, no CR, no system

---

## Security Checklist

These items must be verified before calling Phase 6 complete:

**Player wiki must NEVER show:**
- [ ] `NPC.secrets`
- [ ] `NPC.notes` (GM notes)
- [ ] `Location.gm_notes`
- [ ] `Quest.gm_notes`
- [ ] `Item.gm_notes`
- [ ] `Session.gm_notes`
- [ ] `BestiaryEntry.stat_block`
- [ ] `BestiaryEntry.cr_level`
- [ ] `BestiaryEntry.system`
- [ ] Any `CompendiumEntry` where `is_gm_only=True`
- [ ] Any `MonsterInstance` records (players don't see instances, only the bestiary entry itself if toggled)
- [ ] Edit/create/delete buttons or links of any kind

**Docker must:**
- [ ] Never commit `SECRET_KEY` to git (it's in env vars, not code)
- [ ] Never commit `gm_wiki.db` to the image (it's in a volume)
- [ ] Use gunicorn, not Flask dev server

---

## Testing Checklist

### Player Wiki
- [ ] `/wiki/` lists campaigns
- [ ] `/wiki/<id>/` shows campaign home
- [ ] NPC with `is_player_visible=False` does NOT appear in wiki
- [ ] NPC with `is_player_visible=True` DOES appear in wiki
- [ ] NPC detail never shows `secrets` or `notes` fields
- [ ] Location with `is_player_visible=False` is absent from wiki
- [ ] Quest detail shows `outcome` when status is completed
- [ ] Compendium hides entries where `is_gm_only=True`
- [ ] Bestiary entry detail shows NO stat block, even if entry is visible
- [ ] All wiki pages are truly read-only (no form elements, no edit routes accessible)
- [ ] Wiki works on mobile viewport

### Docker
- [ ] `docker build` succeeds with no errors
- [ ] `docker compose up` starts the app
- [ ] App accessible at `http://localhost:5000`
- [ ] Database file is created in the mapped volume (not inside container)
- [ ] Uploaded images are stored in the mapped volume
- [ ] `docker compose down && docker compose up` — all data still present
- [ ] `SECRET_KEY` environment variable is respected

### Unraid
- [ ] Container appears in Unraid Docker list
- [ ] App accessible from another device on the LAN
- [ ] Container restarts automatically after Unraid reboot
- [ ] Volumes mapped to `/mnt/user/appdata/gm-wiki/`

---

## Git Branch Strategy

```
feature/player-wiki    → Wiki Blueprint, routes, all wiki templates
feature/docker         → Dockerfile, docker-compose, config changes
```

**Suggested commits:**
1. "Add Player Wiki blueprint and base template"
2. "Add wiki routes for NPCs and Locations"
3. "Add wiki routes for Quests, Items, Sessions, Compendium"
4. "Add wiki Bestiary view (no stat blocks)"
5. "Add player visibility toggles to any missing forms"
6. "Add Dockerfile, docker-compose, and gunicorn setup"
7. "Update config.py to read from environment variables"
8. "Add docker-entrypoint.sh for automatic migrations"
9. "Update README with Docker deployment instructions"

**Pull Request:** Merge `feature/player-wiki` to main first, then `feature/docker`.

---

## Future Enhancements (Post-Phase 6)

These are good ideas but out of scope for Phase 6:

- **Player login** — If the wiki ever needs to be internet-accessible, add simple password auth (not needed for local network)
- **Campaign "public" toggle** — A campaign-level switch to enable/disable the player wiki entirely
- **Player-facing session RSVP** — Let players mark themselves as attending upcoming sessions
- **Unraid Community Apps template** — XML template for one-click install from the store
- **Custom domain / reverse proxy** — nginx config for accessing as `gmwiki.local` instead of an IP
- **Dark/light theme toggle for wiki** — The GM view is dark-themed; players might prefer light

---

## Summary

Phase 6 delivers:

✅ Player Wiki — read-only, campaign-scoped, GM secrets hidden
✅ All entity types covered (NPCs, Locations, Quests, Items, Sessions, Compendium, Bestiary)
✅ No new database models needed — flags already exist
✅ Docker container with gunicorn for production use
✅ Persistent volumes for database and uploads
✅ Environment variable configuration for secrets
✅ Unraid-compatible deployment setup

After Phase 6, GM Wiki is a fully self-hosted production app: your players can open the wiki on their phones, and the whole thing runs reliably on your Unraid server.
