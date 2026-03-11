from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from app import db
from app.models import (Campaign, Session, CompendiumEntry, Item, Quest, NPC, Location,
                        CampaignStatTemplate, PlayerCharacter, PlayerCharacterStat,
                        AdventureSite, ActivityLog, Faction, Encounter, EntityMention,
                        RandomTable, Tag, MonsterInstance, Adventure,
                        ICRPGWorld, ICRPGLifeForm, ICRPGType, ICRPGAbility,
                        ICRPGLootDef, ICRPGSpell, ICRPGMilestonePath,
                        CampaignMembership, User)

campaigns_bp = Blueprint('campaigns', __name__, url_prefix='/campaigns')

# Preset stat fields for common game systems.
# Shown as a dropdown on campaign create; GM can edit fields after creation.
STAT_PRESETS = {
    'none': {
        'name': 'None (add stats later)',
        'stats': []
    },
    'dnd5e': {
        'name': 'D&D 5e',
        'stats': [
            'Armor Class (AC)',
            'Max Hit Points',
            'Spell Save DC',
            'Passive Perception',
            'Passive Investigation',
            'Passive Insight',
        ]
    },
    'pathfinder2e': {
        'name': 'Pathfinder 2e',
        'stats': [
            'Armor Class (AC)',
            'Max Hit Points',
            'Perception',
            'Fortitude Save',
            'Reflex Save',
            'Will Save',
            'Class DC',
        ]
    },
    'icrpg': {
        'name': 'ICRPG',
        'stats': [
            'Armor',
            'Hearts (Max HP)',
            'Basic Effort',
            'Weapons/Tools Effort',
            'Magic Effort',
            'Ultimate Effort',
        ]
    },
    'custom': {
        'name': 'Custom (start blank)',
        'stats': []
    },
}


@campaigns_bp.route('/')
@login_required
def list_campaigns():
    campaigns = Campaign.query.filter_by(user_id=current_user.id).order_by(Campaign.name).all()
    return render_template('campaigns/list.html', campaigns=campaigns)


@campaigns_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_campaign():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Campaign name is required.', 'danger')
            return redirect(url_for('campaigns.create_campaign'))

        campaign = Campaign(
            user_id=current_user.id,
            name=name,
            system=request.form.get('system', '').strip(),
            status=request.form.get('status', 'active'),
            description=request.form.get('description', '').strip(),
            image_style_prompt=request.form.get('image_style_prompt', '').strip() or None,
            ai_world_context=request.form.get('ai_world_context', '').strip() or None
        )
        db.session.add(campaign)
        db.session.flush()  # Assigns campaign.id before we create child records

        # Create stat template fields from the chosen preset
        preset_key = request.form.get('stat_preset', 'none')
        preset = STAT_PRESETS.get(preset_key, STAT_PRESETS['none'])
        for order, stat_name in enumerate(preset['stats']):
            field = CampaignStatTemplate(
                campaign_id=campaign.id,
                stat_name=stat_name,
                display_order=order
            )
            db.session.add(field)

        db.session.commit()
        ActivityLog.log_event('created', 'campaign', campaign.name, entity_id=campaign.id)

        # Auto-switch to the newly created campaign
        session['active_campaign_id'] = campaign.id
        flash(f'Campaign "{campaign.name}" created!', 'success')

        return redirect(url_for('adventures.create'))

    return render_template('campaigns/create.html', stat_presets=STAT_PRESETS)


@campaigns_bp.route('/<int:campaign_id>')
@login_required
def campaign_detail(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first_or_404()

    # Aggregate stats for the campaign summary card
    quests = campaign.quests
    adventures = Adventure.query.filter_by(campaign_id=campaign_id).order_by(Adventure.name).all()
    item_count = Item.query.filter_by(campaign_id=campaign_id).count()
    recent_sessions = (Session.query
                       .filter_by(campaign_id=campaign_id)
                       .order_by(Session.number.desc())
                       .limit(5).all())

    stats = {
        'sessions': len(campaign.sessions),
        'npcs': len(campaign.npcs),
        'locations': len(campaign.locations),
        'item_count': item_count,
        'quests_total': len(quests),
        'quests_active': sum(1 for q in quests if q.status == 'active'),
        'quests_completed': sum(1 for q in quests if q.status == 'completed'),
        'adventures_total': len(adventures),
        'adventures_active': sum(1 for a in adventures if a.status == 'Active'),
    }

    return render_template('campaigns/detail.html', campaign=campaign, stats=stats,
                           adventures=adventures, recent_sessions=recent_sessions)


@campaigns_bp.route('/<int:campaign_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_campaign(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Campaign name is required.', 'danger')
            return render_template('campaigns/edit.html', campaign=campaign)
        campaign.name = name
        campaign.system = request.form.get('system', '').strip()
        campaign.status = request.form.get('status', 'active')
        campaign.description = request.form.get('description', '').strip()
        campaign.image_style_prompt = request.form.get('image_style_prompt', '').strip() or None
        campaign.ai_world_context = request.form.get('ai_world_context', '').strip() or None
        campaign.is_public = 'is_public' in request.form
        db.session.commit()
        ActivityLog.log_event('edited', 'campaign', campaign.name, entity_id=campaign.id)
        flash(f'Campaign "{campaign.name}" updated.', 'success')
        return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign.id))

    stat_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()
    return render_template('campaigns/edit.html', campaign=campaign, stat_fields=stat_fields)


# ── Stat template management ─────────────────────────────────────────────────

@campaigns_bp.route('/<int:campaign_id>/stats/add', methods=['POST'])
@login_required
def add_stat_field(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first_or_404()
    stat_name = request.form.get('stat_name', '').strip()
    if not stat_name:
        flash('Stat name cannot be empty.', 'danger')
        return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id))

    # Place new field at the end
    last = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order.desc()).first()
    next_order = (last.display_order + 1) if last else 0

    field = CampaignStatTemplate(
        campaign_id=campaign_id,
        stat_name=stat_name,
        display_order=next_order
    )
    db.session.add(field)
    db.session.flush()  # Assigns field.id before we create PC stat rows

    # Backfill a blank stat row for every existing PC in this campaign
    for pc in PlayerCharacter.query.filter_by(campaign_id=campaign_id).all():
        db.session.add(PlayerCharacterStat(
            character_id=pc.id,
            template_field_id=field.id,
            stat_value=''
        ))

    db.session.commit()
    flash(f'Stat field "{stat_name}" added.', 'success')
    return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')


@campaigns_bp.route('/<int:campaign_id>/stats/<int:stat_id>/rename', methods=['POST'])
@login_required
def rename_stat_field(campaign_id, stat_id):
    field = CampaignStatTemplate.query.filter_by(id=stat_id, campaign_id=campaign_id).first_or_404()
    new_name = request.form.get('stat_name', '').strip()
    if not new_name:
        flash('Stat name cannot be empty.', 'danger')
    else:
        field.stat_name = new_name
        db.session.commit()
        flash('Stat field renamed.', 'success')
    return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')


@campaigns_bp.route('/<int:campaign_id>/stats/<int:stat_id>/delete', methods=['POST'])
@login_required
def delete_stat_field(campaign_id, stat_id):
    field = CampaignStatTemplate.query.filter_by(id=stat_id, campaign_id=campaign_id).first_or_404()
    name = field.stat_name
    db.session.delete(field)
    db.session.commit()
    flash(f'Stat field "{name}" deleted.', 'warning')
    return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')


@campaigns_bp.route('/<int:campaign_id>/stats/<int:stat_id>/move', methods=['POST'])
@login_required
def move_stat_field(campaign_id, stat_id):
    direction = request.form.get('direction')  # 'up' or 'down'
    field = CampaignStatTemplate.query.filter_by(id=stat_id, campaign_id=campaign_id).first_or_404()

    fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()

    idx = next((i for i, f in enumerate(fields) if f.id == stat_id), None)
    if idx is None:
        return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')

    if direction == 'up' and idx > 0:
        swap = fields[idx - 1]
        field.display_order, swap.display_order = swap.display_order, field.display_order
        db.session.commit()
    elif direction == 'down' and idx < len(fields) - 1:
        swap = fields[idx + 1]
        field.display_order, swap.display_order = swap.display_order, field.display_order
        db.session.commit()

    return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')


# ── Delete campaign ───────────────────────────────────────────────────────────

@campaigns_bp.route('/<int:campaign_id>/delete', methods=['POST'])
@login_required
def delete_campaign(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first_or_404()
    name = campaign.name

    # Delete in dependency order so nothing is left referencing a deleted object.

    # Entity mentions reference many entity types — delete first.
    EntityMention.query.filter_by(campaign_id=campaign_id).delete()

    # Encounters reference sessions, arcs, and random tables — delete before those.
    # EncounterMonster rows cascade from Encounter automatically.
    Encounter.query.filter_by(campaign_id=campaign_id).delete()

    # Sessions link to NPCs/Locations/Items/Quests/Monsters — delete next.
    # Cascade on Session.attendances cleans up SessionAttendance rows automatically.
    for sess in list(campaign.sessions):
        db.session.delete(sess)

    # Monster instances link to sessions (many-to-many) — session deletion clears
    # those links, so instances themselves can now be safely deleted.
    MonsterInstance.query.filter_by(campaign_id=campaign_id).delete()

    # ICRPG homebrew catalog entries (only those with campaign_id set).
    # Delete in dependency order: abilities/loot before types, types before worlds.
    ICRPGSpell.query.filter_by(campaign_id=campaign_id).delete()
    ICRPGMilestonePath.query.filter_by(campaign_id=campaign_id).delete()
    ICRPGAbility.query.filter_by(campaign_id=campaign_id).delete()
    ICRPGLootDef.query.filter_by(campaign_id=campaign_id).delete()
    ICRPGType.query.filter_by(campaign_id=campaign_id).delete()
    ICRPGLifeForm.query.filter_by(campaign_id=campaign_id).delete()
    ICRPGWorld.query.filter_by(campaign_id=campaign_id).delete()

    # Player characters — sessions are gone so attendance records are already cleaned
    # up by the Session cascade. ICRPG sheets cascade via PlayerCharacter.icrpg_sheet.
    for pc in list(campaign.player_characters):
        db.session.delete(pc)

    # Compendium entries are standalone.
    CompendiumEntry.query.filter_by(campaign_id=campaign_id).delete()

    # Custom random tables (built-ins have campaign_id=None and are left alone).
    # TableRow rows cascade from RandomTable automatically.
    for table in list(campaign.random_tables):
        db.session.delete(table)

    # Items reference NPCs and Locations via nullable FKs — nullify then delete.
    for item in list(campaign.items):
        item.owner_npc_id = None
        item.origin_location_id = None
        db.session.delete(item)

    # Quests link to NPCs and Locations — clear links then delete.
    for quest in list(campaign.quests):
        quest.involved_npcs = []
        quest.involved_locations = []
        db.session.delete(quest)

    # NPCs reference Locations via home_location_id — nullify then delete.
    for npc in list(campaign.npcs):
        npc.home_location_id = None
        npc.connected_locations = []
        db.session.delete(npc)

    # Locations — nullify parent refs first to avoid self-referential errors.
    for loc in list(campaign.locations):
        loc.parent_location_id = None
    db.session.flush()
    for loc in list(campaign.locations):
        loc.connected_locations = []
        db.session.delete(loc)

    # Adventure sites — NPCs/Locations/Quests/Items that referenced them are
    # already deleted above, so story_arc_id FKs are gone.
    for site in list(campaign.adventure_sites):
        site.tags = []
        site.sessions = []
        db.session.delete(site)

    # Factions — NPCs that referenced them are already deleted.
    Faction.query.filter_by(campaign_id=campaign_id).delete()

    # Tags — association rows (npc_tags, etc.) were cleared when entities were deleted.
    Tag.query.filter_by(campaign_id=campaign_id).delete()

    # Stat template fields are standalone per campaign.
    CampaignStatTemplate.query.filter_by(campaign_id=campaign_id).delete()

    # Clean up activity log entries for this campaign
    ActivityLog.query.filter_by(campaign_id=campaign_id).delete()

    db.session.delete(campaign)
    db.session.commit()
    ActivityLog.log_event('deleted', 'campaign', name, entity_id=campaign_id)

    flash(f'Campaign "{name}" and all its content deleted.', 'warning')
    return redirect(url_for('campaigns.list_campaigns'))


# ---------------------------------------------------------------------------
# Campaign member management (Phase 22)
# ---------------------------------------------------------------------------

@campaigns_bp.route('/<int:campaign_id>/members/add', methods=['POST'])
@login_required
def add_member(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first_or_404()
    username = request.form.get('username', '').strip()
    role = request.form.get('role', 'player')
    if role not in ('player', 'asst_gm'):
        role = 'player'
    user = User.query.filter_by(username=username).first()
    if not user:
        flash(f'No user found with username "{username}".', 'danger')
        return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign_id))
    if user.id == current_user.id:
        flash('You are already the GM of this campaign.', 'warning')
        return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign_id))
    existing = CampaignMembership.query.filter_by(campaign_id=campaign_id, user_id=user.id).first()
    if existing:
        existing.role = role
        db.session.commit()
        flash(f'{username} role updated to {role}.', 'success')
    else:
        membership = CampaignMembership(campaign_id=campaign_id, user_id=user.id, role=role)
        db.session.add(membership)
        # Upgrade user's site role to match if needed
        if role == 'asst_gm' and user.role == 'player':
            user.role = 'asst_gm'
        db.session.commit()
        flash(f'{username} added as {role}.', 'success')
    return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign_id))


@campaigns_bp.route('/<int:campaign_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_member(campaign_id, user_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first_or_404()
    membership = CampaignMembership.query.filter_by(
        campaign_id=campaign_id, user_id=user_id).first_or_404()
    username = membership.user.username
    db.session.delete(membership)
    db.session.commit()
    flash(f'{username} removed from campaign.', 'info')
    return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign_id))


@campaigns_bp.route('/<int:campaign_id>/members/<int:user_id>/role', methods=['POST'])
@login_required
def change_member_role(campaign_id, user_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first_or_404()
    membership = CampaignMembership.query.filter_by(
        campaign_id=campaign_id, user_id=user_id).first_or_404()
    role = request.form.get('role', 'player')
    if role not in ('player', 'asst_gm'):
        role = 'player'
    membership.role = role
    db.session.commit()
    flash(f'{membership.user.username} role changed to {role}.', 'success')
    return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign_id))
