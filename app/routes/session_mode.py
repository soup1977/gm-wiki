from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from app import db
from app.models import Session as GameSession, Quest, Location, NPC

session_mode_bp = Blueprint('session_mode', __name__, url_prefix='/session-mode')


def get_active_campaign_id():
    return session.get('active_campaign_id')


@session_mode_bp.route('/')
def dashboard():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    session['in_session_mode'] = True

    current_session_id = session.get('current_session_id')
    game_session = None
    prev_session = None
    pinned_npcs = []

    # All sessions for the picker (most recent first)
    all_sessions = (
        GameSession.query
        .filter_by(campaign_id=campaign_id)
        .order_by(GameSession.number.desc())
        .all()
    )

    if current_session_id:
        game_session = GameSession.query.filter_by(
            id=current_session_id, campaign_id=campaign_id
        ).first()
        # If the stored session_id doesn't belong to this campaign, clear it
        if not game_session:
            session.pop('current_session_id', None)
            current_session_id = None

    if game_session:
        # Update the session title for the navbar indicator
        title = f"Session #{game_session.number}" if game_session.number else ''
        if game_session.title:
            title = f"{title}: {game_session.title}" if title else game_session.title
        session['session_title'] = title or 'Untitled Session'

        # Pinned NPCs — stored as a JSON list of NPC IDs on the session record
        if game_session.pinned_npc_ids:
            pinned_npcs = NPC.query.filter(
                NPC.id.in_(game_session.pinned_npc_ids),
                NPC.campaign_id == campaign_id
            ).order_by(NPC.name).all()

        # Previous session — highest session number less than the current one
        if game_session.number:
            prev_session = (
                GameSession.query
                .filter_by(campaign_id=campaign_id)
                .filter(GameSession.number < game_session.number)
                .order_by(GameSession.number.desc())
                .first()
            )

    # Active quests for this campaign
    active_quests = (
        Quest.query
        .filter_by(campaign_id=campaign_id, status='active')
        .order_by(Quest.name)
        .all()
    )

    # All locations for the active-location picker
    all_locations = (
        Location.query
        .filter_by(campaign_id=campaign_id)
        .order_by(Location.name)
        .all()
    )

    # All NPCs for the pin-NPCs checklist
    all_npcs = (
        NPC.query
        .filter_by(campaign_id=campaign_id)
        .order_by(NPC.name)
        .all()
    )

    return render_template(
        'session_mode/dashboard.html',
        game_session=game_session,
        all_sessions=all_sessions,
        current_session_id=current_session_id,
        active_quests=active_quests,
        all_locations=all_locations,
        all_npcs=all_npcs,
        pinned_npcs=pinned_npcs,
        prev_session=prev_session,
    )


@session_mode_bp.route('/set-session', methods=['POST'])
def set_session():
    sess_id = request.form.get('session_id', '').strip()
    if sess_id:
        session['current_session_id'] = int(sess_id)
    else:
        session.pop('current_session_id', None)
    return redirect(url_for('session_mode.dashboard'))


@session_mode_bp.route('/set-location', methods=['POST'])
def set_location():
    campaign_id = get_active_campaign_id()
    current_session_id = session.get('current_session_id')
    if not campaign_id or not current_session_id:
        return redirect(url_for('session_mode.dashboard'))

    game_session = GameSession.query.filter_by(
        id=current_session_id, campaign_id=campaign_id
    ).first_or_404()

    loc_id = request.form.get('location_id', '').strip()
    game_session.active_location_id = int(loc_id) if loc_id else None
    db.session.commit()
    return redirect(url_for('session_mode.dashboard'))


@session_mode_bp.route('/pin-npcs', methods=['POST'])
def pin_npcs():
    campaign_id = get_active_campaign_id()
    current_session_id = session.get('current_session_id')
    if not campaign_id or not current_session_id:
        return redirect(url_for('session_mode.dashboard'))

    game_session = GameSession.query.filter_by(
        id=current_session_id, campaign_id=campaign_id
    ).first_or_404()

    npc_ids = [int(x) for x in request.form.getlist('pinned_npc_ids')]
    game_session.pinned_npc_ids = npc_ids
    db.session.commit()
    flash('Pinned NPCs updated.', 'success')
    return redirect(url_for('session_mode.dashboard'))


@session_mode_bp.route('/add-note', methods=['POST'])
def add_note():
    campaign_id = get_active_campaign_id()
    current_session_id = session.get('current_session_id')
    if not campaign_id or not current_session_id:
        return redirect(url_for('session_mode.dashboard'))

    game_session = GameSession.query.filter_by(
        id=current_session_id, campaign_id=campaign_id
    ).first_or_404()

    note = request.form.get('note', '').strip()
    if note:
        timestamp = datetime.utcnow().strftime('%H:%M')
        new_line = f"**[{timestamp}]** {note}"
        if game_session.gm_notes:
            game_session.gm_notes = game_session.gm_notes + '\n\n' + new_line
        else:
            game_session.gm_notes = new_line
        db.session.commit()
        flash('Note added to session.', 'success')

    return redirect(url_for('session_mode.dashboard'))
