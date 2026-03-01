# Future Roles & Permissions System

## Current State (as of Phase 19e)

The app has two effective roles:

- **Admin** (GM): `User.is_admin = True`. Full control over all entities, campaigns, and users.
- **Regular User** (player): `User.is_admin = False`. Can claim PCs, edit their own claimed characters within allowed bounds, and view the player wiki.

PC-level permissions are handled by:
- `PlayerCharacter.user_id` — the claiming player (NULL = unclaimed)
- `ICRPGCharacterSheet.allow_player_edit` — per-PC toggle for stat/effort editing (Phase 19e)

There is no campaign-scoped role system. A user is either admin everywhere or a player everywhere.

---

## Proposed Future Roles

| Role | Scope | Description |
|------|-------|-------------|
| **Player** | Per-campaign | Can view wiki, claim PCs, edit own sheet within allowed bounds |
| **Assistant GM** | Per-campaign | Can edit entities, run session mode, manage sessions, but not manage campaign settings or users |
| **GM** | Per-campaign | Full campaign control — edit all entities, manage settings, assign roles within their campaign |
| **Admin** | Global | Server admin — manages all campaigns, all users, system settings |

---

## Permission Matrix

| Action | Player | Asst GM | GM | Admin |
|--------|--------|---------|----|-------|
| View player wiki | Yes | Yes | Yes | Yes |
| Claim / edit own PC sheet | Yes | Yes | Yes | Yes |
| Add/remove own loot & abilities | Yes | Yes | Yes | Yes |
| Edit own base stats (with toggle) | Per-PC toggle | Yes | Yes | Yes |
| Create/edit NPCs | No | Yes | Yes | Yes |
| Create/edit Locations | No | Yes | Yes | Yes |
| Create/edit Quests | No | Yes | Yes | Yes |
| Create/edit Items | No | Yes | Yes | Yes |
| Create/edit Factions | No | Yes | Yes | Yes |
| Create/edit Compendium | No | Yes | Yes | Yes |
| Manage Sessions | No | Yes | Yes | Yes |
| Run Session Mode | No | Yes | Yes | Yes |
| Manage Encounters | No | Yes | Yes | Yes |
| Edit Adventure Sites (Story Arcs) | No | Yes | Yes | Yes |
| Manage Bestiary | No | Yes | Yes | Yes |
| Run Combat Tracker | No | Yes | Yes | Yes |
| ICRPG Catalog CRUD | No | Yes | Yes | Yes |
| Edit other players' PCs | No | No | Yes | Yes |
| Manage Campaign Settings | No | No | Yes | Yes |
| Assign roles within campaign | No | No | Yes | Yes |
| Create/delete campaigns | No | No | Yes | Yes |
| Manage Users (approve, ban) | No | No | No | Yes |
| System Settings | No | No | No | Yes |

---

## Suggested Implementation

### New Model: `CampaignMembership`

```python
class CampaignMembership(db.Model):
    __tablename__ = 'campaign_memberships'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    role        = db.Column(db.String(20), default='player')  # player | assistant_gm | gm
    joined_at   = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'campaign_id'),)
```

### Migration Path

1. Create `CampaignMembership` table
2. Backfill: for each campaign, create a `gm` membership for `campaign.user_id`
3. Add helper: `current_user.campaign_role(campaign_id)` returning the role string
4. Replace `current_user.is_admin` checks in routes with role-based checks
5. Keep `User.is_admin` as a global override (Admin role)
6. Update templates to use `campaign_role` instead of `is_admin`

### Wiki Replacement

With proper roles, the separate wiki routes (`/wiki/...`) could be replaced by the main app routes with role-based visibility:
- Players see entities filtered by `is_player_visible`
- Players don't see GM-only fields (secrets, hooks, notes)
- The main routes handle both GM and player views based on role

This eliminates template duplication between GM views and wiki views.
