# Phase 22 — User Roles: GM / Asst GM / Player

## Context

The app currently has one user type: everyone who logs in is a GM (or admin). There is a read-only `/wiki/` view but it's unauthenticated and largely unused. The goal of Phase 22 is to give actual player accounts a meaningful, personalized experience without exposing GM-only information.

### Decisions locked in
1. One user can have multiple PCs across multiple campaigns.
2. Reveals (read-aloud) persist in DB — once the GM reveals a room it stays visible until un-revealed.
3. Players can edit their own PC sheet.
4. Revealed locations appear in the player's location list.
5. Players see: their own PCs, revealed locations, public compendium, public items, public quests/npcs.
6. Replace the anonymous `/wiki/` with a proper per-user logged-in player experience.
7. **New user default role: `player`** — GM must escalate to `gm` or `asst_gm` via admin or campaign member UI.
8. **Asst GM**: identical to GM for all content access (secrets, GM notes, etc.) — only excluded from site-level user management (`is_admin` actions).
9. **Player PC sheet edit**: if campaign system is ICRPG → use the existing ICRPG character sheet edit UI; otherwise → use the base PC edit form. System is read from `campaign.system`.

---

## Roles

| Role | Description |
|---|---|
| `gm` | Full access to everything in their campaigns. |
| `asst_gm` | Same as GM for a specific campaign (trusted co-GM). |
| `player` | Sees only their own PCs and GM-revealed content in campaigns they're part of. |

`is_admin` stays for site-level admin (user management, setup). Role is campaign-agnostic on the User model, but campaign membership is tracked via a new `CampaignMembership` table so a user can be a player in Campaign A and a GM in Campaign B.

---

## Data Model Changes

### 1. `User.role` — site-level default role
```python
# Add to User model
role = db.Column(db.String(20), default='gm')  # 'gm', 'asst_gm', 'player'
```
Existing users get `role='gm'` in the migration. The site admin (`is_admin=True`) always has full access regardless.

### 2. `CampaignMembership` — who is in which campaign and at what role
```python
class CampaignMembership(db.Model):
    __tablename__ = 'campaign_memberships'
    id           = db.Column(db.Integer, primary_key=True)
    campaign_id  = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role         = db.Column(db.String(20), default='player')  # 'gm', 'asst_gm', 'player'
    joined_at    = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('campaign_id', 'user_id'),)
```
The campaign owner (`campaign.user_id`) is implicitly GM — no membership row required, but one can be added for completeness.

### 3. `AdventureRoom.is_revealed` — persistent DB flag
Currently reveal state lives in Flask `session` (lost on browser close). Move to a proper DB column:
```python
is_revealed = db.Column(db.Boolean, default=False)
```
GM toggles this via the existing `/rooms/<id>/reveal` endpoint. Players see the room read-aloud when `is_revealed=True`.

### 4. `PlayerCharacter.user_id` — already exists ✓
The link is already there. Phase 22 uses it to show a player their own characters.

---

## Access Control

### Helper decorators / functions (new file: `app/routes/auth_helpers.py`)
```python
def gm_required(f):
    """Decorator: blocks players from GM views."""

def campaign_access_required(f):
    """Decorator: user must be a member of the campaign (any role)."""

def is_gm_of(campaign):
    """Returns True if current_user owns or is gm/asst_gm of campaign."""

def is_player_of(campaign):
    """Returns True if current_user is a player member of campaign."""
```

### Route protection strategy
- All existing GM routes: add `gm_required` (blocks `player`-role users; `asst_gm` passes through)
- `asst_gm` has full content access — only `is_admin` routes are blocked for them
- New player routes: `login_required` only, then check campaign membership role inside
- The `/wiki/` routes: deprecated; redirect to `/player/` for logged-in users

---

## New: Player Dashboard (`/player/`)

Replaces the anonymous `/wiki/` as the player-facing experience.

### Blueprint: `app/routes/player.py`
| URL | Template | Description |
|---|---|---|
| `GET /player/` | `player/dashboard.html` | Home — my campaigns, my PCs |
| `GET /player/campaign/<id>/` | `player/campaign_home.html` | Campaign overview (revealed entities only) |
| `GET /player/campaign/<id>/locations/` | `player/locations.html` | Revealed locations list |
| `GET /player/campaign/<id>/locations/<loc_id>/` | `player/location_detail.html` | Revealed location detail |
| `GET /player/campaign/<id>/npcs/` | `player/npcs.html` | Player-visible NPCs |
| `GET /player/campaign/<id>/quests/` | `player/quests.html` | Player-visible quests |
| `GET /player/campaign/<id>/compendium/` | `player/compendium.html` | Public compendium entries |
| `GET /player/campaign/<id>/items/` | `player/items.html` | Player-visible items (incl. their loot) |
| `GET /player/pc/<pc_id>/` | `player/pc_sheet.html` | Own PC sheet — edit routes to ICRPG sheet UI if system=icrpg, else base form |

### What players see per entity type
| Entity | Condition to show |
|---|---|
| Location | `is_player_visible=True` OR (`is_revealed=True` on a linked AdventureRoom) |
| NPC | `is_player_visible=True` |
| Quest | `is_player_visible=True` |
| Item | `is_player_visible=True` OR `owner_pc_id` = one of their PCs |
| Compendium | `is_player_visible=True` (already exists) |
| AdventureRoom read-aloud | `is_revealed=True` (shown on location detail) |

---

## GM: Campaign Member Management

New UI in campaign detail page — "Members" section:
- List current members with role badges
- Invite by username (creates `CampaignMembership` row)
- Change role (player ↔ asst_gm)
- Remove member

### Routes (add to `app/routes/campaigns.py`)
| Method | URL | Action |
|---|---|---|
| `POST` | `/campaigns/<id>/members/add` | Add user as member |
| `POST` | `/campaigns/<id>/members/<uid>/role` | Change role |
| `POST` | `/campaigns/<id>/members/<uid>/remove` | Remove member |

---

## GM: Reveal Controls

The GM already has a [Reveal] button in the adventure runner that toggles `session['revealed_rooms']`. After this phase:
- Toggle writes to `AdventureRoom.is_revealed` in DB instead of Flask session
- Runner still shows the blurred/unblurred read-aloud state for the GM
- Players on `/player/campaign/<id>/locations/` see the location card with read-aloud text when `is_revealed=True`

### Entity-level reveal (non-room entities)
For NPCs, Quests, Items, Locations — the existing `is_player_visible` toggle (already in detail pages) serves this purpose. No new field needed — just make sure player routes filter on it.

---

## Navbar Changes

Current navbar is GM-only. After Phase 22:
- If `current_user.role == 'player'` (and not admin): show simplified navbar → Player Dashboard, My PCs
- If GM: show current navbar unchanged
- Admin always sees full nav

---

## What Gets Deprecated

- `/wiki/` routes: keep the blueprint but add a redirect to `/player/` for logged-in users; keep anonymous access showing a "please log in" message. No templates deleted — just redirected.

---

## Migration

Two migrations needed:
1. Add `User.role` column (default `'gm'` for all existing users)
2. Create `campaign_memberships` table
3. Add `AdventureRoom.is_revealed` column (default `False`)

---

## All Files to Create/Modify

| File | Change |
|---|---|
| `app/models.py` | Add `User.role`, `CampaignMembership` model, `AdventureRoom.is_revealed` |
| `migrations/versions/` | 3 new migrations (or one combined) |
| `app/routes/auth_helpers.py` | **Create** — `gm_required`, `is_gm_of`, `is_player_of` helpers |
| `app/routes/player.py` | **Create** — player dashboard blueprint |
| `app/templates/player/` | **Create** — dashboard, campaign_home, locations, location_detail, npcs, quests, items, compendium, pc_sheet |
| `app/templates/base.html` | Conditional navbar (GM vs player view) |
| `app/routes/campaigns.py` | Member management routes (add/role/remove) |
| `app/templates/campaigns/detail.html` | Members section (invite, list, remove) |
| `app/routes/adventures.py` | `toggle_reveal` writes to `AdventureRoom.is_revealed` instead of Flask session |
| `app/routes/auth.py` | Set `role` on new user registration (default `player` for self-signup, `gm` for admin-created) |
| `app/templates/auth/` | Admin user creation: role dropdown |
| `app/routes/admin.py` | Role field on user edit |
| `app/__init__.py` | Register `player` blueprint |
| `app/routes/wiki.py` | Add redirect to `/player/` for logged-in users |

---

## Feature Table

| Feature | Status | Notes |
|---|---|---|
| `User.role` field + migration | Pending | Default 'gm' for existing users |
| `CampaignMembership` table + migration | Pending | Tracks who is in which campaign |
| `AdventureRoom.is_revealed` DB field + migration | Pending | Replaces Flask session reveal |
| `gm_required` decorator | Pending | Blocks player-role users from GM views |
| Player blueprint + routes | Pending | `/player/` URL space |
| Player dashboard template | Pending | My campaigns + my PCs |
| Campaign home (player view) | Pending | Revealed content only |
| Revealed locations list + detail | Pending | Filter on is_revealed + is_player_visible |
| Player-visible NPCs/Quests/Items/Compendium | Pending | Filter on is_player_visible |
| Own PC sheet (view + edit own stats) | Pending | Edit gated by user_id match |
| Campaign member management UI | Pending | In campaign detail page |
| Invite by username | Pending | POST /campaigns/<id>/members/add |
| Toggle reveal → writes to DB | Pending | adventures.py toggle_reveal fix |
| Conditional navbar (GM vs player) | Pending | base.html |
| Role-aware user creation/edit | Pending | New users default `player`; role dropdown in admin user edit |
| PC sheet edit routing by system | Pending | ICRPG → ICRPG sheet edit; other → base form |

---

## Verification

1. Create a new user via admin → assign `role='player'`
2. Add that user as a member of a campaign
3. Log in as the player → see Player Dashboard with their campaigns and PCs
4. GM reveals a room in adventure runner → player's location list shows it with read-aloud text
5. GM marks an NPC `is_player_visible=True` → player sees it in their NPCs list
6. Player opens their PC sheet → can edit their own stats; cannot see another player's PC
7. Player tries to navigate to `/campaigns/` → redirected or blocked (gm_required)
8. Asst GM logs in → full GM view for that campaign
