# CLAUDE.md — The War Table Project Briefing

## What This Project Is
The War Table is a local, browser-based tool for tabletop RPG Game Masters. It lets a GM manage multiple campaigns, each containing NPCs, Locations, Quests, Sessions, Items, and Compendium entries — all cross-linked and clickable. It also has a read-only player-facing wiki view.

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

## Project Structure
```
gm-wiki/
├── app/
│   ├── __init__.py         # App factory — creates and configures the Flask app
│   ├── models.py           # All database models (SQLAlchemy)
│   ├── ai_provider.py      # Claude AI integration (Smart Fill, Generate)
│   ├── sd_provider.py      # Stable Diffusion image generation
│   ├── obsidian_parser.py  # Obsidian vault file parser
│   ├── routes/             # One Blueprint per feature (~30 files)
│   │   ├── main.py         # Homepage, campaign switching
│   │   ├── auth.py         # Login, signup, setup, logout
│   │   ├── admin.py        # User management (admin only)
│   │   ├── campaigns.py    # Campaign CRUD + stat templates
│   │   ├── npcs.py, locations.py, quests.py, items.py, sessions.py
│   │   ├── compendium.py, factions.py, pcs.py, encounters.py
│   │   ├── bestiary.py, monsters.py, tables.py, tags.py
│   │   ├── session_mode.py # Live session dashboard
│   │   ├── combat.py       # Combat tracker
│   │   ├── wiki.py         # Player-facing read-only wiki
│   │   ├── ai.py, sd_generate.py, quick_create.py
│   │   ├── global_search.py, entity_search.py
│   │   ├── obsidian_import.py, srd_import.py, bestiary_import.py
│   │   └── settings.py
│   ├── seed_data/          # ICRPG bestiary + table JSON files
│   ├── templates/          # Jinja2 HTML templates (~70 files)
│   │   ├── base.html       # Shared layout with navbar
│   │   ├── wiki/           # Player-facing wiki templates
│   │   └── ...             # One folder per entity type
│   └── static/
│       ├── css/custom.css
│       └── js/             # Global search, dice roller, quick create, etc.
├── migrations/versions/    # Flask-Migrate (Alembic) migration files
├── docs/                   # Phase plans and user guide
├── instance/
│   └── gm_wiki.db          # SQLite database (auto-created, not in git)
├── config.py               # App configuration
├── run.py                  # Entry point (port 5001)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh
└── update.sh               # Unraid deployment update script
```

---

## Build Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Scaffold, Flask, campaign CRUD, navigation | Complete |
| 2 | NPCs + Locations with bidirectional linking | Complete |
| 3 | Quests, Sessions, Items, Compendium | Complete |
| 4 | Images, file uploads, Markdown rendering, tags/filtering | Complete |
| 5 | Combat tracker, random tables, session mode dashboard | Complete |
| 5.5 | Bestiary + monster instances | Complete |
| 6 | Player wiki view, Docker packaging, Unraid deployment | Complete |
| 7 | AI Smart Fill, SRD import, settings | Complete |
| 7.5 | Auth, admin, factions, encounters, PCs, shortcodes, global search, Obsidian import, dice roller, quick create, SD image generation | Complete |
| 8 | Security audit, hardening, documentation | Complete |
| 9 | Adventure Sites entity (Markdown doc per area, sticky ToC, run state) | Complete |
| 10 | Campaign Assistant (AI chat, per-feature provider selection) | Complete |
| 11 | Entity-from-selection (text-select → create NPC/Location/Quest/Item in Adventure Sites) | Complete |
| 12 | Session Workflow (carryover, post-session wrap-up, "Start Session Here" button) | Complete |
| 13 | UX Polish (status badge system, campaign stats, grouped global search, wiki visibility toggle) | Complete — PR #9 |
| 14 | AI Runtime Features (Improv Encounter, Hazard Flavor, Suggest Consequences, Suggest Milestones) | Complete |
| 15a | Dashboard Overhaul — site content in Session Mode, shortcode popup previews | Complete — PRs #12, #13 |
| 15b | Dashboard Overhaul — panel layout, pinned entities, map overlay, drag-to-rearrange | Planned — see docs/phase-15-plan.md |
| 15.5 | Story Arcs rename (UI), editable AI prompts in Settings, Generate Entry fix | Complete — PR #14 |
| 16 | Workflow Guidance (campaign wizard, planning checklist, entity grouping, theme toggle) | Planned — see docs/phase-16-plan.md |
| 17 | AI Campaign Genesis (genesis wizard, entity-arc linking, arc-aware AI, campaign quick-start) | Complete |
| 18 | Arc-Session Workflow (encounter arc-linking, richer arc doc, encounters on session form, arc-aware prefill) | Complete — PR #19 |
| 19a | ICRPG Character Sheet Builder — catalog models, seed data, CLI command | Complete — PR #20 |
| 19b | ICRPG Character Sheet View + Quick Edit (AJAX HP/hero coin/equip) | Complete — PR #20 |
| 19c | ICRPG Character Creation Wizard (8-step multi-step form) | Complete — PR #20 |
| 19d | ICRPG Homebrew Catalog CRUD, Add Loot/Ability UI, wiki/combat integration | Complete — PR #21 |
| 19e | Player Sheet Permissions (loot/ability for owners, per-PC stat toggle) | Complete — PR #22 |
| 19f | ICRPG Loot & Ability Mechanics (effects parser, smart filtering, slot costs, effect badges) | Complete — PR #23 |
| 19g | Active Effects Display (collapsible text effects from equipped loot & abilities) | Complete — see docs/phase-19g-plan.md |
| 19h | ICRPG catalog edit fix + import-to-homebrew for all entity types | Complete — PR #49 |
| 19i | ICRPG catalog description preview columns (Life Forms, Types, Loot) | Complete — PR #50 |
| 19j | ICRPG catalog friendly JSON editors (stat grids, tier accordion) + Type manage modal | Complete — PR #51, see docs/phase-19j-plan.md |
| 19k | Anthropic model selector in Settings (Haiku / Sonnet / Opus dropdown) | Complete — PR #52, see docs/phase-19k-plan.md |

---

## Key Rules to Always Follow

### Never break these:
- GM-only fields (Secrets, GM Notes) must **never** appear in player-facing views
- Each campaign is self-contained — no data bleeds between campaigns
- The app must work well on a tablet at a live game table (readable, fast, minimal clicks)
- System-agnostic — no hardcoded D&D, ICRPG, or other system references

### Phase planning:
- **Always save phase plans to `docs/phase-N-plan.md`** when a new phase is discussed or its feature list is provided — never rely on conversation context alone
- **The plan file MUST be saved to `docs/` as the FIRST step after plan approval, BEFORE any code implementation begins.** This is non-negotiable — the plan doc is the source of truth.
- Each plan file must include a feature table (Feature | Status | Notes) and any split/dependency notes
- Update the Build Phases table in this file when a phase is completed or a new one is defined

### Code style:
- Use Flask application factory pattern (`create_app()` in `app/__init__.py`)
- Use Blueprints for routes — one Blueprint per entity type
- Use Flask-SQLAlchemy for all database work
- Bootstrap 5 for all UI — avoid writing custom CSS unless necessary
- Keep templates DRY — use `base.html` for the shared layout

---

## Entity Types (Summary)
Each entity type is its own page, cross-linked to others. See `docs/data-model.md` for the full hierarchy.

1. **NPCs** — name, role, status, home location, faction, portrait, secrets (GM only). Can be campaign-wide or adventure-specific (`adventure_id`). Campaign NPCs can be "featured" in an adventure via `adventure_npc_link` M-to-M without losing their campaign scope.
2. **Player Characters** — name, class, stats from campaign template, player-claimed
3. **Locations** — campaign-wide world records (nestable, map images, GM notes). Adventure Scenes and adventure Locations (see #13) can link to these.
4. **Quests** — Campaign quests (`adventure_id=NULL`, gold [Campaign] badge) span multiple adventures; Adventure quests (`adventure_id=X`, blue [Adventure] badge) are scoped to one adventure. Campaign quests are linked to specific adventures via `adventure_quest_link` M-to-M.
5. **Sessions** — number, date, summary, linked NPCs/locations/items/quests, PC attendance. `adventure_id` FK links to the adventure being run.
6. **Items** — name, type, rarity, owner (NPC or party), origin location
7. **Factions** — name, disposition, linked NPCs/locations/quests
8. **Compendium** — custom rules reference, per-campaign, GM-only toggle
9. **Bestiary** — global monster entries (not campaign-scoped), spawn instances per campaign
10. **Encounters** — linked monsters, loot tables, tied to sessions
11. **Random Tables** — weighted entries, one-click rolling, builtin + custom
12. **Story Arcs** — one Markdown doc per adventure area; sticky ToC, run state, AI brainstorm/ideas/session-prep. UI label is "Story Arcs"; code/DB/URLs use `adventure_site`. Shortcode: `#site[Name]`
13. **Adventures** — structured campaign modules: Acts → Scenes → Locations. UI calls them "Locations"; DB table is `adventure_room`, Python class `AdventureRoom`. Each location has read-aloud text, GM notes, creatures, loot, hazards, and an optional link to a campaign Location record. The Adventure Runner is the at-table play interface (right panel: Combat, Session, NPCs, AI Tools, Tables tabs).

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
1. Run `git stash list` AND `git status` — if a stash exists or the working tree is dirty, STOP and alert Craig before doing anything else
2. If there is a stash, ask whether to apply it, commit it to a branch, or leave it — NEVER silently abandon stash work
3. Confirm we're on the correct base branch, then create: `git checkout -b feature/<short-description>`
4. Do all work on that branch
5. At the end, remind Craig to commit and open a PR to merge into `main`

**Never code directly on `main`** for anything bigger than a typo fix or single-line tweak.

### Stash Safety Rules — CRITICAL
**Stash work is WIP that has not been committed. It is easy to lose.**
- **At session start**: Always run `git stash list`. If any stash exists, surface it to Craig immediately.
- **Before any branch switch**: Run `git stash list` AND `git status`. If there is a stash or uncommitted changes, do NOT switch branches until Craig has decided what to do with them.
- **If a stash is found**: Describe what's in it (`git stash show stash@{N}`) and ask Craig: "Apply it, commit it to a branch, or intentionally discard it?"
- **Never silently switch branches when a stash or dirty working tree exists.**

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

## Documentation
- Phase plans live in `docs/` (one per build phase)
- User guide: `docs/user-guide.md`
