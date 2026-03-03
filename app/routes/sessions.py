from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from app import db
from app.models import (Session, NPC, Location, Item, Quest, Tag, session_tags,
                        get_or_create_tags, PlayerCharacter, SessionAttendance,
                        MonsterInstance, AdventureSite, Encounter, ActivityLog)
from app.shortcode import process_shortcodes, clear_mentions

sessions_bp = Blueprint('sessions', __name__)

_SESSION_TEXT_FIELDS = ['prep_notes', 'summary', 'gm_notes']


def get_active_campaign_id():
    return session.get('active_campaign_id')


def _save_attendance(sess, campaign_id):
    """Clear existing attendance records for this session and recreate from
    the 'attended_pc_ids' checkbox list in the current request form."""
    for att in list(sess.attendances):
        db.session.delete(att)
    db.session.flush()

    attended_ids = {int(i) for i in request.form.getlist('attended_pc_ids')}
    for pc_id in attended_ids:
        db.session.add(SessionAttendance(session_id=sess.id, character_id=pc_id))


@sessions_bp.route('/sessions')
@login_required
def list_sessions():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    session.pop('in_session_mode', None)
    session.pop('current_session_id', None)
    session.pop('session_title', None)

    active_tag = request.args.get('tag', '').strip().lower() or None
    query = Session.query.filter_by(campaign_id=campaign_id)
    if active_tag:
        query = query.join(Session.tags).filter(Tag.name == active_tag)
    sessions_list = query.order_by(Session.number.desc()).all()

    all_tags = sorted(
        {tag for s in Session.query.filter_by(campaign_id=campaign_id).all() for tag in s.tags},
        key=lambda t: t.name
    )
    return render_template('sessions/list.html', sessions=sessions_list, all_tags=all_tags, active_tag=active_tag)


@sessions_bp.route('/sessions/new', methods=['GET', 'POST'])
@login_required
def create_session():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    items = Item.query.filter_by(campaign_id=campaign_id).order_by(Item.name).all()
    quests = Quest.query.filter_by(campaign_id=campaign_id).order_by(Quest.name).all()
    pcs = PlayerCharacter.query.filter_by(campaign_id=campaign_id)\
        .order_by(PlayerCharacter.character_name).all()
    monsters = MonsterInstance.query.filter_by(campaign_id=campaign_id)\
        .order_by(MonsterInstance.instance_name).all()
    all_sites = AdventureSite.query.filter_by(campaign_id=campaign_id)\
        .order_by(AdventureSite.sort_order, AdventureSite.name).all()
    # Encounters available to plan (not yet assigned to a session)
    encounters = Encounter.query.filter_by(campaign_id=campaign_id, session_id=None)\
        .order_by(Encounter.name).all()

    if request.method == 'POST':
        date_str = request.form.get('date_played', '').strip()
        parsed_date = None
        if date_str:
            try:
                parsed_date = date.fromisoformat(date_str)
            except ValueError:
                flash('Invalid date format. Use YYYY-MM-DD.', 'danger')
                return render_template('sessions/form.html', sess=None,
                                       npcs=npcs, locations=locations,
                                       items=items, quests=quests, pcs=pcs,
                                       monsters=monsters, all_sites=all_sites,
                                       encounters=encounters)

        sess = Session(
            campaign_id=campaign_id,
            number=request.form.get('number') or None,
            title=request.form.get('title', '').strip() or None,
            date_played=parsed_date,
            prep_notes=request.form.get('prep_notes', '').strip() or None,
            summary=request.form.get('summary', '').strip() or None,
            gm_notes=request.form.get('gm_notes', '').strip() or None,
        )

        sess.npcs_featured = NPC.query.filter(
            NPC.id.in_(request.form.getlist('npcs_featured')),
            NPC.campaign_id == campaign_id
        ).all()
        sess.locations_visited = Location.query.filter(
            Location.id.in_(request.form.getlist('locations_visited')),
            Location.campaign_id == campaign_id
        ).all()
        sess.items_mentioned = Item.query.filter(
            Item.id.in_(request.form.getlist('items_mentioned')),
            Item.campaign_id == campaign_id
        ).all()
        sess.quests_touched = Quest.query.filter(
            Quest.id.in_(request.form.getlist('quests_touched')),
            Quest.campaign_id == campaign_id
        ).all()
        sess.monsters_encountered = MonsterInstance.query.filter(
            MonsterInstance.id.in_(request.form.getlist('monsters_encountered')),
            MonsterInstance.campaign_id == campaign_id
        ).all()

        site_id = request.form.get('adventure_site_id')
        if site_id:
            site = AdventureSite.query.filter_by(id=int(site_id), campaign_id=campaign_id).first()
            sess.adventure_sites = [site] if site else []
        else:
            sess.adventure_sites = []

        sess.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))
        db.session.add(sess)
        db.session.flush()  # Need sess.id before creating attendance rows and linking encounters

        # Link selected encounters to this session
        selected_enc_ids = {int(i) for i in request.form.getlist('encounters_planned')}
        for enc in Encounter.query.filter(
            Encounter.id.in_(selected_enc_ids),
            Encounter.campaign_id == campaign_id
        ).all():
            enc.session_id = sess.id

        _save_attendance(sess, campaign_id)
        sess.is_player_visible = 'is_player_visible' in request.form

        for field in _SESSION_TEXT_FIELDS:
            val = getattr(sess, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'session', sess.id)
                setattr(sess, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()
        label = f'Session {sess.number}' if sess.number else 'Session'
        ActivityLog.log_event('created', 'session', sess.title or label, entity_id=sess.id, campaign_id=campaign_id)
        flash(f'{label} created.', 'success')
        return redirect(url_for('sessions.session_detail', session_id=sess.id))

    # Check for preselect_site_id from query param (e.g. "Start Session Here" on Site detail)
    preselect_site_id = request.args.get('site_id', type=int)

    # Arc-aware prefill: if coming from a specific Story Arc, pre-select its entities
    arc_npc_ids = set()
    arc_location_ids = set()
    arc_quest_ids = set()
    arc_encounter_ids = set()
    arc_site = None
    arc_next_milestone = None

    if preselect_site_id:
        arc_site = AdventureSite.query.filter_by(id=preselect_site_id, campaign_id=campaign_id).first()
        if arc_site:
            arc_npc_ids       = {n.id for n in NPC.query.filter_by(campaign_id=campaign_id, story_arc_id=preselect_site_id).all()}
            arc_location_ids  = {l.id for l in Location.query.filter_by(campaign_id=campaign_id, story_arc_id=preselect_site_id).all()}
            arc_quest_ids     = {q.id for q in Quest.query.filter_by(campaign_id=campaign_id, story_arc_id=preselect_site_id).all()}
            arc_encounter_ids = {e.id for e in Encounter.query.filter_by(campaign_id=campaign_id, story_arc_id=preselect_site_id, session_id=None).all()}
            for m in arc_site.get_milestones():
                if not m.get('done'):
                    arc_next_milestone = m['label']
                    break

    return render_template('sessions/form.html', sess=None,
                           npcs=npcs, locations=locations,
                           items=items, quests=quests, pcs=pcs,
                           monsters=monsters, all_sites=all_sites,
                           encounters=encounters,
                           preselect_site_id=preselect_site_id,
                           arc_site=arc_site, arc_next_milestone=arc_next_milestone,
                           arc_npc_ids=arc_npc_ids, arc_location_ids=arc_location_ids,
                           arc_quest_ids=arc_quest_ids, arc_encounter_ids=arc_encounter_ids)


@sessions_bp.route('/sessions/<int:session_id>')
@login_required
def session_detail(session_id):
    campaign_id = get_active_campaign_id()
    sess = Session.query.filter_by(id=session_id, campaign_id=campaign_id).first_or_404()

    if request.args.get('from') != 'session':
        session.pop('in_session_mode', None)
        session.pop('current_session_id', None)
        session.pop('session_title', None)

    return render_template('sessions/detail.html', sess=sess)


@sessions_bp.route('/sessions/<int:session_id>/next')
@login_required
def create_next_session(session_id):
    """Create a new session form pre-populated with carryover from the previous session."""
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    prev = Session.query.filter_by(id=session_id, campaign_id=campaign_id).first_or_404()

    # Build carryover data
    next_number = (prev.number + 1) if prev.number else None
    carryover_quest_ids = {q.id for q in prev.quests_touched if q.status == 'active'}
    carryover_npc_ids = {n.id for n in prev.npcs_featured if n.status in ('alive', 'unknown')}
    carryover_site_id = None
    for s in prev.adventure_sites:
        if s.status == 'Active':
            carryover_site_id = s.id
            break
    carryover_pc_ids = {pc.id for pc in prev.attending_pcs}

    carryover = {
        'from_session': prev,
        'next_number': next_number,
        'quest_ids': carryover_quest_ids,
        'npc_ids': carryover_npc_ids,
        'site_id': carryover_site_id,
        'pc_ids': carryover_pc_ids,
    }

    # Fetch all entity lists for the form
    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    items = Item.query.filter_by(campaign_id=campaign_id).order_by(Item.name).all()
    quests = Quest.query.filter_by(campaign_id=campaign_id).order_by(Quest.name).all()
    pcs = PlayerCharacter.query.filter_by(campaign_id=campaign_id)\
        .order_by(PlayerCharacter.character_name).all()
    monsters = MonsterInstance.query.filter_by(campaign_id=campaign_id)\
        .order_by(MonsterInstance.instance_name).all()
    all_sites = AdventureSite.query.filter_by(campaign_id=campaign_id)\
        .order_by(AdventureSite.sort_order, AdventureSite.name).all()
    encounters = Encounter.query.filter_by(campaign_id=campaign_id, session_id=None)\
        .order_by(Encounter.name).all()

    return render_template('sessions/form.html', sess=None,
                           npcs=npcs, locations=locations,
                           items=items, quests=quests, pcs=pcs,
                           monsters=monsters, all_sites=all_sites,
                           encounters=encounters,
                           preselect_site_id=None,
                           carryover=carryover,
                           arc_site=None, arc_next_milestone=None,
                           arc_npc_ids=set(), arc_location_ids=set(),
                           arc_quest_ids=set(), arc_encounter_ids=set())


@sessions_bp.route('/sessions/<int:session_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_session(session_id):
    campaign_id = get_active_campaign_id()
    sess = Session.query.filter_by(id=session_id, campaign_id=campaign_id).first_or_404()

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    items = Item.query.filter_by(campaign_id=campaign_id).order_by(Item.name).all()
    quests = Quest.query.filter_by(campaign_id=campaign_id).order_by(Quest.name).all()
    pcs = PlayerCharacter.query.filter_by(campaign_id=campaign_id)\
        .order_by(PlayerCharacter.character_name).all()
    monsters = MonsterInstance.query.filter_by(campaign_id=campaign_id)\
        .order_by(MonsterInstance.instance_name).all()
    all_sites = AdventureSite.query.filter_by(campaign_id=campaign_id)\
        .order_by(AdventureSite.sort_order, AdventureSite.name).all()
    # Encounters available to plan: unassigned ones + ones already linked to this session
    encounters = Encounter.query.filter(
        Encounter.campaign_id == campaign_id,
        db.or_(Encounter.session_id == None, Encounter.session_id == sess.id)
    ).order_by(Encounter.name).all()

    if request.method == 'POST':
        date_str = request.form.get('date_played', '').strip()
        parsed_date = None
        if date_str:
            try:
                parsed_date = date.fromisoformat(date_str)
            except ValueError:
                flash('Invalid date format. Use YYYY-MM-DD.', 'danger')
                return render_template('sessions/form.html', sess=sess,
                                       npcs=npcs, locations=locations,
                                       items=items, quests=quests, pcs=pcs,
                                       monsters=monsters, all_sites=all_sites,
                                       encounters=encounters)

        sess.number = request.form.get('number') or None
        sess.title = request.form.get('title', '').strip() or None
        sess.date_played = parsed_date
        sess.prep_notes = request.form.get('prep_notes', '').strip() or None
        sess.summary = request.form.get('summary', '').strip() or None
        sess.gm_notes = request.form.get('gm_notes', '').strip() or None

        sess.npcs_featured = NPC.query.filter(
            NPC.id.in_(request.form.getlist('npcs_featured')),
            NPC.campaign_id == campaign_id
        ).all()
        sess.locations_visited = Location.query.filter(
            Location.id.in_(request.form.getlist('locations_visited')),
            Location.campaign_id == campaign_id
        ).all()
        sess.items_mentioned = Item.query.filter(
            Item.id.in_(request.form.getlist('items_mentioned')),
            Item.campaign_id == campaign_id
        ).all()
        sess.quests_touched = Quest.query.filter(
            Quest.id.in_(request.form.getlist('quests_touched')),
            Quest.campaign_id == campaign_id
        ).all()
        sess.monsters_encountered = MonsterInstance.query.filter(
            MonsterInstance.id.in_(request.form.getlist('monsters_encountered')),
            MonsterInstance.campaign_id == campaign_id
        ).all()

        site_id = request.form.get('adventure_site_id')
        if site_id:
            site = AdventureSite.query.filter_by(id=int(site_id), campaign_id=campaign_id).first()
            sess.adventure_sites = [site] if site else []
        else:
            sess.adventure_sites = []

        # Update encounter–session links: select new, deselect removed
        selected_enc_ids = {int(i) for i in request.form.getlist('encounters_planned')}
        for enc in encounters:
            if enc.id in selected_enc_ids:
                enc.session_id = sess.id
            else:
                enc.session_id = None

        sess.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))
        _save_attendance(sess, campaign_id)
        sess.is_player_visible = 'is_player_visible' in request.form

        clear_mentions('session', sess.id)
        for field in _SESSION_TEXT_FIELDS:
            val = getattr(sess, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'session', sess.id)
                setattr(sess, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()
        ActivityLog.log_event('edited', 'session', sess.title or f'Session {sess.number}', entity_id=sess.id, campaign_id=campaign_id)
        flash('Session updated.', 'success')
        return redirect(url_for('sessions.session_detail', session_id=sess.id))

    return render_template('sessions/form.html', sess=sess,
                           npcs=npcs, locations=locations,
                           items=items, quests=quests, pcs=pcs,
                           monsters=monsters, all_sites=all_sites,
                           encounters=encounters,
                           arc_site=None, arc_next_milestone=None,
                           arc_npc_ids=set(), arc_location_ids=set(),
                           arc_quest_ids=set(), arc_encounter_ids=set())


@sessions_bp.route('/sessions/<int:session_id>/delete', methods=['POST'])
@login_required
def delete_session(session_id):
    campaign_id = get_active_campaign_id()
    sess = Session.query.filter_by(id=session_id, campaign_id=campaign_id).first_or_404()
    label = f'Session {sess.number}' if sess.number else 'Session'
    db.session.delete(sess)
    db.session.commit()
    ActivityLog.log_event('deleted', 'session', sess.title or label, entity_id=session_id, campaign_id=campaign_id)
    flash(f'{label} deleted.', 'success')
    return redirect(url_for('sessions.list_sessions'))
