from collections import defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from app import db
from app.models import Quest, NPC, Location, Tag, quest_tags, get_or_create_tags, Faction
from app.shortcode import process_shortcodes, clear_mentions, resolve_mentions_for_target

quests_bp = Blueprint('quests', __name__)

_QUEST_TEXT_FIELDS = ['hook', 'description', 'outcome', 'gm_notes']

QUEST_STATUSES = ['active', 'completed', 'failed', 'on_hold']
# Fixed order for grouped list view — most actionable first
QUEST_STATUS_ORDER = ['active', 'on_hold', 'completed', 'failed']


def get_active_campaign_id():
    return session.get('active_campaign_id')


@quests_bp.route('/quests')
@login_required
def list_quests():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    session.pop('in_session_mode', None)
    session.pop('current_session_id', None)
    session.pop('session_title', None)

    active_tag = request.args.get('tag', '').strip().lower() or None
    query = Quest.query.filter_by(campaign_id=campaign_id)
    if active_tag:
        query = query.join(Quest.tags).filter(Tag.name == active_tag)
    quests = query.order_by(Quest.name).all()

    all_tags = sorted(
        {tag for q in Quest.query.filter_by(campaign_id=campaign_id).all() for tag in q.tags},
        key=lambda t: t.name
    )

    # Group by status in fixed order (active first)
    groups = defaultdict(list)
    for quest in quests:
        groups[quest.status or 'active'].append(quest)
    grouped_quests = {
        status: groups[status]
        for status in QUEST_STATUS_ORDER
        if groups[status]
    }

    return render_template('quests/list.html', quests=quests, grouped_quests=grouped_quests,
                           all_tags=all_tags, active_tag=active_tag)


@quests_bp.route('/quests/new', methods=['GET', 'POST'])
@login_required
def create_quest():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    factions = Faction.query.filter_by(campaign_id=campaign_id).order_by(Faction.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Quest name is required.', 'danger')
            return render_template('quests/form.html', quest=None,
                                   npcs=npcs, locations=locations,
                                   statuses=QUEST_STATUSES, factions=factions)

        faction_id_val = request.form.get('faction_id')
        quest = Quest(
            campaign_id=campaign_id,
            name=name,
            status=request.form.get('status', 'active'),
            hook=request.form.get('hook', '').strip() or None,
            description=request.form.get('description', '').strip() or None,
            outcome=request.form.get('outcome', '').strip() or None,
            gm_notes=request.form.get('gm_notes', '').strip() or None,
            faction_id=int(faction_id_val) if faction_id_val else None,
        )

        # Many-to-many: involved NPCs
        selected_npc_ids = request.form.getlist('involved_npcs')
        quest.involved_npcs = NPC.query.filter(
            NPC.id.in_(selected_npc_ids), NPC.campaign_id == campaign_id
        ).all()

        # Many-to-many: involved Locations
        selected_location_ids = request.form.getlist('involved_locations')
        quest.involved_locations = Location.query.filter(
            Location.id.in_(selected_location_ids), Location.campaign_id == campaign_id
        ).all()

        quest.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))
        quest.is_player_visible = 'is_player_visible' in request.form
        db.session.add(quest)

        db.session.flush()

        for field in _QUEST_TEXT_FIELDS:
            val = getattr(quest, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'quest', quest.id)
                setattr(quest, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()
        flash(f'Quest "{quest.name}" created.', 'success')
        return redirect(url_for('quests.quest_detail', quest_id=quest.id))

    return render_template('quests/form.html', quest=None,
                           npcs=npcs, locations=locations,
                           statuses=QUEST_STATUSES, factions=factions)


@quests_bp.route('/quests/<int:quest_id>')
@login_required
def quest_detail(quest_id):
    campaign_id = get_active_campaign_id()
    quest = Quest.query.filter_by(id=quest_id, campaign_id=campaign_id).first_or_404()

    if request.args.get('from') != 'session':
        session.pop('in_session_mode', None)
        session.pop('current_session_id', None)
        session.pop('session_title', None)

    mentions = resolve_mentions_for_target('quest', quest_id)
    return render_template('quests/detail.html', quest=quest, mentions=mentions)


@quests_bp.route('/quests/<int:quest_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_quest(quest_id):
    campaign_id = get_active_campaign_id()
    quest = Quest.query.filter_by(id=quest_id, campaign_id=campaign_id).first_or_404()

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    factions = Faction.query.filter_by(campaign_id=campaign_id).order_by(Faction.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Quest name is required.', 'danger')
            return render_template('quests/form.html', quest=quest,
                                   npcs=npcs, locations=locations,
                                   statuses=QUEST_STATUSES, factions=factions)

        quest.name = name
        quest.status = request.form.get('status', 'active')
        quest.hook = request.form.get('hook', '').strip() or None
        quest.description = request.form.get('description', '').strip() or None
        quest.outcome = request.form.get('outcome', '').strip() or None
        quest.gm_notes = request.form.get('gm_notes', '').strip() or None
        faction_id_val = request.form.get('faction_id')
        quest.faction_id = int(faction_id_val) if faction_id_val else None

        selected_npc_ids = request.form.getlist('involved_npcs')
        quest.involved_npcs = NPC.query.filter(
            NPC.id.in_(selected_npc_ids), NPC.campaign_id == campaign_id
        ).all()

        selected_location_ids = request.form.getlist('involved_locations')
        quest.involved_locations = Location.query.filter(
            Location.id.in_(selected_location_ids), Location.campaign_id == campaign_id
        ).all()

        quest.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))
        quest.is_player_visible = 'is_player_visible' in request.form

        clear_mentions('quest', quest.id)
        for field in _QUEST_TEXT_FIELDS:
            val = getattr(quest, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'quest', quest.id)
                setattr(quest, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()
        flash(f'Quest "{quest.name}" updated.', 'success')
        return redirect(url_for('quests.quest_detail', quest_id=quest.id))

    return render_template('quests/form.html', quest=quest,
                           npcs=npcs, locations=locations,
                           statuses=QUEST_STATUSES, factions=factions)


@quests_bp.route('/quests/<int:quest_id>/delete', methods=['POST'])
@login_required
def delete_quest(quest_id):
    campaign_id = get_active_campaign_id()
    quest = Quest.query.filter_by(id=quest_id, campaign_id=campaign_id).first_or_404()
    name = quest.name
    db.session.delete(quest)
    db.session.commit()
    flash(f'Quest "{name}" deleted.', 'success')
    return redirect(url_for('quests.list_quests'))
