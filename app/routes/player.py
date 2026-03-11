"""
player.py — Player-facing dashboard blueprint (Phase 22).

URL space: /player/

Players see only:
  - Campaigns they are members of
  - Their own PCs
  - Locations marked is_player_visible=True OR with a revealed AdventureRoom (is_revealed=True)
  - NPCs, Quests, Items, Compendium entries marked is_player_visible=True
  - Items where owner_pc_id matches one of their PCs

GMs landing here are redirected to the GM dashboard.
"""

from flask import Blueprint, render_template, redirect, url_for, abort, flash
from flask_login import login_required, current_user
from app.models import (
    Campaign, CampaignMembership, PlayerCharacter, Location,
    NPC, Quest, Item, CompendiumEntry, AdventureRoom
)
from app import db

player_bp = Blueprint('player', __name__, url_prefix='/player')


def _get_player_campaigns():
    """Return campaigns the current user is a member of OR owns."""
    owned = Campaign.query.filter_by(user_id=current_user.id).all()
    memberships = CampaignMembership.query.filter_by(user_id=current_user.id).all()
    member_campaign_ids = {m.campaign_id for m in memberships}
    # Combine, deduplicate
    owned_ids = {c.id for c in owned}
    extra = Campaign.query.filter(
        Campaign.id.in_(member_campaign_ids - owned_ids)
    ).all()
    return owned + extra


def _player_owns_campaign(campaign):
    """True if current user is a member (any role) or owner of this campaign."""
    if campaign.user_id == current_user.id:
        return True
    return CampaignMembership.query.filter_by(
        campaign_id=campaign.id, user_id=current_user.id
    ).first() is not None


def _revealed_location_ids(campaign_id):
    """Return set of campaign Location IDs linked to any revealed AdventureRoom."""
    rooms = AdventureRoom.query.filter_by(is_revealed=True).join(
        AdventureRoom.scene
    ).all()
    ids = set()
    for room in rooms:
        if room.location_id and room.scene.act.adventure.campaign_id == campaign_id:
            ids.add(room.location_id)
    return ids


# ---------------------------------------------------------------------------
# Dashboard — my campaigns + my PCs
# ---------------------------------------------------------------------------

@player_bp.route('/')
@login_required
def dashboard():
    # GMs go to the main GM dashboard
    if current_user.role in ('gm', 'asst_gm') or current_user.is_admin:
        return redirect(url_for('main.index'))

    campaigns = _get_player_campaigns()
    my_pcs = PlayerCharacter.query.filter_by(user_id=current_user.id).all()
    return render_template('player/dashboard.html',
                           campaigns=campaigns,
                           my_pcs=my_pcs)


# ---------------------------------------------------------------------------
# Campaign home (player view)
# ---------------------------------------------------------------------------

@player_bp.route('/campaign/<int:campaign_id>/')
@login_required
def campaign_home(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if not _player_owns_campaign(campaign):
        abort(403)

    revealed_loc_ids = _revealed_location_ids(campaign_id)
    locations = Location.query.filter(
        Location.campaign_id == campaign_id,
        db.or_(Location.is_player_visible == True, Location.id.in_(revealed_loc_ids))
    ).order_by(Location.name).all()

    npcs = NPC.query.filter_by(campaign_id=campaign_id, is_player_visible=True).order_by(NPC.name).all()
    quests = Quest.query.filter_by(campaign_id=campaign_id, is_player_visible=True).order_by(Quest.name).all()

    my_pc_ids = [pc.id for pc in PlayerCharacter.query.filter_by(
        campaign_id=campaign_id, user_id=current_user.id).all()]
    items = Item.query.filter(
        Item.campaign_id == campaign_id,
        db.or_(Item.is_player_visible == True, Item.owner_pc_id.in_(my_pc_ids) if my_pc_ids else db.false())
    ).order_by(Item.name).all()

    my_pcs = PlayerCharacter.query.filter_by(
        campaign_id=campaign_id, user_id=current_user.id).order_by(PlayerCharacter.character_name).all()

    return render_template('player/campaign_home.html',
                           campaign=campaign,
                           locations=locations,
                           npcs=npcs,
                           quests=quests,
                           items=items,
                           my_pcs=my_pcs,
                           revealed_loc_ids=revealed_loc_ids)


# ---------------------------------------------------------------------------
# PC sheet (view + edit own stats)
# ---------------------------------------------------------------------------

@player_bp.route('/pc/<int:pc_id>/')
@login_required
def pc_sheet(pc_id):
    pc = PlayerCharacter.query.get_or_404(pc_id)
    # Must be the owner
    if pc.user_id != current_user.id:
        abort(403)
    # Redirect to the GM-side PC detail page — it handles both ICRPG and generic sheets
    return redirect(url_for('pcs.pc_detail', pc_id=pc_id))
