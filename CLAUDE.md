# CLAUDE.md — GM Wiki Project Briefing

## What This Project Is
GM Wiki is a local, browser-based tool for tabletop RPG Game Masters. It lets a GM manage multiple campaigns, each containing NPCs, Locations, Quests, Sessions, Items, and Compendium entries — all cross-linked and clickable. It also has a read-only player-facing wiki view.

It runs in a Docker container on an Unraid home server and is accessed via browser on the local network. No internet required.

---

## Who I Am
- I'm Craig, a self-taught developer. My background is VB.NET in Visual Studio.
- I'm learning Python and Flask through this project.
- **Please explain new concepts in plain English before using them in code.**
- Tell me if I'm about to do something the wrong way *before* I do it.
- Keep code changes focused — don't refactor unrelated things without asking.

---

## Tech Stack
- **Backend:** Python + Flask
- **Database:** SQLite (via Flask-SQLAlchemy)
- **Templating:** Jinja2
- **Frontend:** Bootstrap 5
- **Hosting:** Docker on Unraid
- **Version Control:** GitHub — explain branch/commit/push steps clearly

---

## Project Structure (once scaffolded)
```
gm-wiki/
├── app/
│   ├── __init__.py         # App factory — creates and configures the Flask app
│   ├── models.py           # All database models (SQLAlchemy)
│   ├── routes/             # One file per entity type
│   │   ├── main.py         # Homepage, campaign switching
│   │   ├── campaigns.py
│   │   ├── npcs.py
│   │   ├── locations.py
│   │   ├── quests.py
│   │   ├── sessions.py
│   │   ├── items.py
│   │   └── compendium.py
│   ├── templates/          # Jinja2 HTML templates
│   │   ├── base.html       # Shared layout with navbar
│   │   └── ...             # One folder per entity type
│   └── static/             # CSS, JS, images
│       └── css/
│           └── custom.css
├── instance/
│   └── gm_wiki.db          # SQLite database (auto-created, not in git)
├── CLAUDE.md               # This file
├── README.md
├── requirements.txt
├── config.py               # App configuration
├── run.py                  # Entry point to start the app
└── Dockerfile              # Added in Phase 6
```

---

## Build Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Scaffold, Flask running, campaign CRUD, navigation | 🔄 In Progress |
| 2 | NPCs + Locations with bidirectional linking | Not started |
| 3 | Quests, Sessions, Items, Compendium | Not started |
| 4 | Images, file uploads, Markdown rendering, tags/filtering | Not started |
| 5 | Combat tracker, random tables, session mode dashboard | Not started |
| 6 | Player wiki view, Docker packaging, Unraid deployment | Not started |

---

## Key Rules to Always Follow

### Never break these:
- GM-only fields (Secrets, GM Notes) must **never** appear in player-facing views
- Each campaign is self-contained — no data bleeds between campaigns
- The app must work well on a tablet at a live game table (readable, fast, minimal clicks)
- System-agnostic — no hardcoded D&D, ICRPG, or other system references

### Code style:
- Use Flask application factory pattern (`create_app()` in `app/__init__.py`)
- Use Blueprints for routes — one Blueprint per entity type
- Use Flask-SQLAlchemy for all database work
- Bootstrap 5 for all UI — avoid writing custom CSS unless necessary
- Keep templates DRY — use `base.html` for the shared layout

---

## Entity Types (Summary)
Each entity type is its own page, cross-linked to others.

1. **NPCs** — name, role, status, home location, faction, portrait, secrets (GM only)
2. **Locations** — name, type, parent location (nestable), map image, GM notes
3. **Quests** — name, status, hook, involved NPCs/locations, GM notes
4. **Sessions** — number, date, summary, linked NPCs/locations/items/quests
5. **Items** — name, type, rarity, owner (NPC or party), origin location
6. **Compendium** — custom rules reference, per-campaign, GM-only toggle

---

## GitHub Workflow
- One milestone per phase
- One branch per feature (e.g. `feature/npc-crud`)
- Pull request to merge into main, even solo
- Descriptive commit messages (e.g. `"Add campaign create form and database model"`)

### Branching Rules — IMPORTANT
**Before starting any significant change, create a feature branch.** A "significant change" is anything that:
- Adds a new route file, Blueprint, or template folder
- Adds or modifies database models
- Touches more than 2–3 files
- Could break existing functionality if something goes wrong

**Steps Claude must follow at the start of a significant task:**
1. Check `git status` to confirm we're on `main` and working tree is clean
2. Create a branch: `git checkout -b feature/<short-description>`
3. Do all work on that branch
4. At the end, remind Craig to commit and open a PR to merge into `main`

**Never code directly on `main`** for anything bigger than a typo fix or single-line tweak.

If the work is already done on `main` (like this session), remind Craig to retroactively create a branch using:
```
git checkout -b feature/<short-description>
# (work is already here)
git push -u origin feature/<short-description>
```
Then open a PR to make the merge intentional and reviewable.

---

## Unraid Deployment

- **Server path:** `/mnt/user/appdata/gm-wiki/`
- **Method:** Git clone + `docker compose up` (no Docker Hub image)
- **Update script:** `update.sh` in the project root — run it on the Unraid server to pull latest code, rebuild, and restart
- **To update:** SSH into Unraid, then: `bash /mnt/user/appdata/gm-wiki/update.sh`
- **Volumes:** `./instance` (SQLite DB) and `./uploads` (images) persist across rebuilds
- **Migrations run automatically** on container start via `docker-entrypoint.sh`

---

## Scope Reference
Full detailed scope lives in `gm-wiki-scope-reference.md` in the project root.
When in doubt about what a feature should do, check there first.
