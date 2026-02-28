# The War Table

A self-hosted, browser-based campaign management tool for tabletop RPG Game Masters. Manage NPCs, locations, quests, items, sessions, and more — all cross-linked and searchable. Includes a read-only player wiki that hides GM secrets.

Built with Python/Flask and SQLite. Runs in Docker on a home server.

---

## Features

### Campaign Management
- Multiple campaigns with independent data
- Per-campaign stat templates (D&D 5e, Pathfinder 2e, ICRPG, or custom)
- Campaign switching from any page

### Entity Types
- **NPCs** — role, status, faction, portrait, secrets (GM only), connected locations
- **Player Characters** — stats from campaign template, player-claimed, session attendance
- **Locations** — nestable parent/child hierarchy, connected locations, map uploads
- **Quests** — status tracking (active/on hold/completed/failed), linked NPCs and locations
- **Sessions** — date, summary, linked entities, PC attendance, GM prep notes
- **Items** — type, rarity, owner NPC, origin location, images
- **Factions** — disposition tracking, linked to NPCs, locations, and quests
- **Compendium** — custom rules reference entries, GM-only toggle
- **Bestiary** — global monster entries, spawn instances per campaign
- **Encounters** — link monsters, set loot tables
- **Random Tables** — weighted entries, one-click rolling, ICRPG seed data

### Cross-Linking
- Entity mention shortcodes in any text field (`#npc[Name]`, `#loc[Name]`, etc.)
- "Referenced by" back-links on detail pages
- Quick-create modal for new entities from dropdowns

### Live Game Tools
- **Session Mode** — dashboard for running a live session with prep notes, active location, and timestamped notes
- **Combat Tracker** — initiative tracking, HP management, quick-add from bestiary
- **Dice Roller** — supports standard notation (2d6+3), advantage/disadvantage, roll history

### Player Wiki
- Read-only view at `/wiki/` — no login required
- Shows only entities marked "Player Visible"
- GM Notes, Secrets, and GM Hooks are never exposed

### Import Tools
- Obsidian vault import (NPC, Location, Compendium from Markdown files)
- D&D 5e SRD import (browse and import Open5e content)
- ICRPG bestiary and random table seed data

### AI Features (Optional)
- Smart Fill — paste raw text to auto-fill entity forms (requires Anthropic API key)
- AI-generated entries from a concept prompt
- Stable Diffusion image generation (requires local SD instance)

### Admin
- Multi-user with admin/player roles
- User creation, password reset, account deletion
- Toggle open registration on/off

---

## Tech Stack

- **Backend:** Python 3.11 + Flask
- **Database:** SQLite via Flask-SQLAlchemy
- **Frontend:** Bootstrap 5, Jinja2 templates
- **Deployment:** Docker + Gunicorn
- **Migrations:** Flask-Migrate (Alembic)

---

## Quick Start (Local Development)

```bash
git clone https://github.com/YOUR_USERNAME/gm-wiki.git
cd gm-wiki
pip install -r requirements.txt
python3 run.py
```

Open `http://localhost:5001` in your browser. On first visit, you'll be prompted to create an admin account.

---

## Docker Deployment

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/gm-wiki.git
cd gm-wiki

# Create .env file with a secret key
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" > .env

# Build and start
docker compose up -d
```

The app runs on port **5001**. Database and uploads persist in `./instance/` and `./uploads/`.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes (production) | Flask session signing key |
| `ANTHROPIC_API_KEY` | No | Enables AI Smart Fill features |
| `FLASK_ENV` | No | Set to `development` for debug mode |

---

## Updating (Unraid)

SSH into the Unraid server and run:

```bash
bash /mnt/user/appdata/gm-wiki/update.sh
```

This pulls latest code, rebuilds the Docker image, and restarts the container. Database migrations run automatically on startup.

---

## Documentation

- [User Guide](docs/user-guide.md) — How to use The War Table
- [CLAUDE.md](CLAUDE.md) — Project conventions for AI-assisted development
