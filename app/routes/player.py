"""
player.py — Player-facing dashboard blueprint (Phase 22).

Self-service player flow:
1. Log in → Player Dashboard (my campaigns + my PCs)
2. "Join a Campaign" → list of public campaigns → click to join (creates CampaignMembership)
3. "Create Character" → ICRPG wizard (if ICRPG campaign) or normal PC create form
4. View revealed locations, visible NPCs/quests/items, compendium

GMs landing here are redirected to the GM dashboard.
"""

from flask import (Blueprint, render_template, redirect, url_for,
                   abort, flash, request, session)
from flask_login import login_required, current_user
from app.models import (
    Campaign, CampaignMembership, PlayerCharacter, Location,
    NPC, Quest, Item, AdventureRoom
)
from app.shortcode import resolve_mentions_for_target
from app import db

player_bp = Blueprint('player', __name__, url_prefix='/player')


def _get_player_campaigns():
    """Return campaigns the current user is a member of OR owns."""
    owned = Campaign.query.filter_by(user_id=current_user.id).all()
    memberships = CampaignMembership.query.filter_by(user_id=current_user.id).all()
    member_campaign_ids = {m.campaign_id for m in memberships}
    owned_ids = {c.id for c in owned}
    extra = Campaign.query.filter(
        Campaign.id.in_(member_campaign_ids - owned_ids)
    ).all() if member_campaign_ids - owned_ids else []
    return owned + extra


def _player_can_access(campaign):
    """True if current user owns or is a member of this campaign."""
    if campaign.user_id == current_user.id:
        return True
    return CampaignMembership.query.filter_by(
        campaign_id=campaign.id, user_id=current_user.id
    ).first() is not None


def _revealed_location_ids(campaign_id):
    """Return set of campaign Location IDs linked to any revealed AdventureRoom."""
    ids = set()
    rooms = (AdventureRoom.query
             .filter_by(is_revealed=True)
             .join(AdventureRoom.scene)
             .all())
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

    my_campaigns = _get_player_campaigns()
    my_pcs = PlayerCharacter.query.filter_by(user_id=current_user.id).all()
    return render_template('player/dashboard.html',
                           my_campaigns=my_campaigns,
                           my_pcs=my_pcs)


# ---------------------------------------------------------------------------
# Browse & join public campaigns
# ---------------------------------------------------------------------------

@player_bp.route('/join/')
@login_required
def browse_campaigns():
    """List public campaigns the player hasn't joined yet."""
    already_in = {c.id for c in _get_player_campaigns()}
    public_campaigns = Campaign.query.filter_by(is_public=True, status='active').all()
    available = [c for c in public_campaigns if c.id not in already_in]
    return render_template('player/browse_campaigns.html', campaigns=available)


@player_bp.route('/join/<int:campaign_id>', methods=['POST'])
@login_required
def join_campaign(campaign_id):
    """Create a CampaignMembership and redirect to that campaign's player home."""
    campaign = Campaign.query.get_or_404(campaign_id)
    if not campaign.is_public:
        abort(403)
    existing = CampaignMembership.query.filter_by(
        campaign_id=campaign_id, user_id=current_user.id).first()
    if not existing:
        membership = CampaignMembership(
            campaign_id=campaign_id, user_id=current_user.id, role='player')
        db.session.add(membership)
        db.session.commit()
        flash(f'You joined {campaign.name}!', 'success')
    # Set this campaign active in Flask session so PC create forms work
    session['active_campaign_id'] = campaign_id
    return redirect(url_for('player.campaign_home', campaign_id=campaign_id))


# ---------------------------------------------------------------------------
# Campaign home (player view)
# ---------------------------------------------------------------------------

@player_bp.route('/campaign/<int:campaign_id>/')
@login_required
def campaign_home(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if not _player_can_access(campaign):
        abort(403)

    # Set as active campaign so PC forms work
    session['active_campaign_id'] = campaign_id

    revealed_loc_ids = _revealed_location_ids(campaign_id)
    locations = Location.query.filter(
        Location.campaign_id == campaign_id,
        db.or_(Location.is_player_visible == True,
               Location.id.in_(revealed_loc_ids) if revealed_loc_ids else db.false())
    ).order_by(Location.name).all()

    npcs = NPC.query.filter_by(campaign_id=campaign_id, is_player_visible=True)\
               .order_by(NPC.name).all()
    quests = Quest.query.filter_by(campaign_id=campaign_id, is_player_visible=True)\
                  .order_by(Quest.name).all()

    my_pc_ids = [pc.id for pc in PlayerCharacter.query.filter_by(
        campaign_id=campaign_id, user_id=current_user.id).all()]
    items = Item.query.filter(
        Item.campaign_id == campaign_id,
        db.or_(
            Item.is_player_visible == True,
            Item.owner_pc_id.in_(my_pc_ids) if my_pc_ids else db.false()
        )
    ).order_by(Item.name).all()

    my_pcs = PlayerCharacter.query.filter_by(
        campaign_id=campaign_id, user_id=current_user.id
    ).order_by(PlayerCharacter.character_name).all()

    system = (campaign.system or '').lower()
    is_icrpg = 'icrpg' in system

    return render_template('player/campaign_home.html',
                           campaign=campaign,
                           locations=locations,
                           npcs=npcs,
                           quests=quests,
                           items=items,
                           my_pcs=my_pcs,
                           revealed_loc_ids=revealed_loc_ids,
                           is_icrpg=is_icrpg)


# ---------------------------------------------------------------------------
# Player entity detail views (player_view=True hides GM-only fields)
# ---------------------------------------------------------------------------

def _player_can_see_location(loc, campaign_id):
    revealed_ids = _revealed_location_ids(campaign_id)
    return loc.is_player_visible or loc.id in revealed_ids


def _player_can_see_item(item, campaign_id):
    if item.is_player_visible:
        return True
    my_pc_ids = [pc.id for pc in PlayerCharacter.query.filter_by(
        campaign_id=campaign_id, user_id=current_user.id).all()]
    return item.owner_pc_id in my_pc_ids if my_pc_ids else False


@player_bp.route('/campaign/<int:campaign_id>/npc/<int:npc_id>/')
@login_required
def player_npc_detail(campaign_id, npc_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if not _player_can_access(campaign):
        abort(403)
    npc = NPC.query.get_or_404(npc_id)
    if npc.campaign_id != campaign_id or not npc.is_player_visible:
        abort(403)
    session['active_campaign_id'] = campaign_id
    mentions = resolve_mentions_for_target('npc', npc_id)
    return render_template('npcs/detail.html', npc=npc, mentions=mentions, player_view=True)


@player_bp.route('/campaign/<int:campaign_id>/location/<int:location_id>/')
@login_required
def player_location_detail(campaign_id, location_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if not _player_can_access(campaign):
        abort(403)
    location = Location.query.get_or_404(location_id)
    if location.campaign_id != campaign_id or not _player_can_see_location(location, campaign_id):
        abort(403)
    session['active_campaign_id'] = campaign_id
    mentions = resolve_mentions_for_target('loc', location_id)
    ancestors = []
    current = location.parent_location
    while current and len(ancestors) < 10:
        ancestors.append(current)
        current = current.parent_location
    ancestors.reverse()
    return render_template('locations/detail.html', location=location,
                           mentions=mentions, ancestors=ancestors, player_view=True)


@player_bp.route('/campaign/<int:campaign_id>/quest/<int:quest_id>/')
@login_required
def player_quest_detail(campaign_id, quest_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if not _player_can_access(campaign):
        abort(403)
    quest = Quest.query.get_or_404(quest_id)
    if quest.campaign_id != campaign_id or not quest.is_player_visible:
        abort(403)
    session['active_campaign_id'] = campaign_id
    mentions = resolve_mentions_for_target('quest', quest_id)
    return render_template('quests/detail.html', quest=quest, mentions=mentions, player_view=True)


@player_bp.route('/campaign/<int:campaign_id>/item/<int:item_id>/')
@login_required
def player_item_detail(campaign_id, item_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if not _player_can_access(campaign):
        abort(403)
    item = Item.query.get_or_404(item_id)
    if item.campaign_id != campaign_id or not _player_can_see_item(item, campaign_id):
        abort(403)
    session['active_campaign_id'] = campaign_id
    mentions = resolve_mentions_for_target('item', item_id)
    return render_template('items/detail.html', item=item, mentions=mentions, player_view=True)


# ---------------------------------------------------------------------------
# PC sheet — view own PC (redirects to appropriate system sheet)
# ---------------------------------------------------------------------------

@player_bp.route('/pc/<int:pc_id>/')
@login_required
def pc_sheet(pc_id):
    pc = PlayerCharacter.query.get_or_404(pc_id)
    if pc.user_id != current_user.id:
        abort(403)
    # Set active campaign so sheet routes work
    session['active_campaign_id'] = pc.campaign_id
    return redirect(url_for('pcs.pc_detail', pc_id=pc_id))
