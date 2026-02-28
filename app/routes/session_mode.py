from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required
from app import db
from app.models import Session as GameSession, Quest, Location, Encounter, NPC, Item

session_mode_bp = Blueprint('session_mode', __name__, url_prefix='/session-mode')


def get_active_campaign_id():
    return session.get('active_campaign_id')


@session_mode_bp.route('/')
@login_required
def dashboard():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    session['in_session_mode'] = True

    current_session_id = session.get('current_session_id')
    game_session = None
    prev_session = None

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

    # Encounters linked to the active session
    session_encounters = (
        Encounter.query
        .filter_by(session_id=current_session_id)
        .order_by(Encounter.name)
        .all()
    ) if current_session_id else []

    # Quests specifically linked to this session (shown in Column 1)
    session_quests = game_session.quests_touched if game_session else []
    other_active_count = len([q for q in active_quests
                               if not game_session or q not in session_quests])

    return render_template(
        'session_mode/dashboard.html',
        game_session=game_session,
        all_sessions=all_sessions,
        current_session_id=current_session_id,
        active_quests=active_quests,
        all_locations=all_locations,
        prev_session=prev_session,
        session_encounters=session_encounters,
        session_quests=session_quests,
        other_active_count=other_active_count,
    )


@session_mode_bp.route('/set-session', methods=['POST'])
@login_required
def set_session():
    sess_id = request.form.get('session_id', '').strip()
    if sess_id:
        session['current_session_id'] = int(sess_id)
    else:
        session.pop('current_session_id', None)
    return redirect(url_for('session_mode.dashboard'))


@session_mode_bp.route('/set-location', methods=['POST'])
@login_required
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


@session_mode_bp.route('/add-note', methods=['POST'])
@login_required
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


@session_mode_bp.route('/post-session')
@login_required
def post_session():
    """Post-session wrap-up page — lets the GM quickly update quest/NPC statuses
    and write a session summary without navigating to each entity individually."""
    campaign_id = get_active_campaign_id()
    current_session_id = session.get('current_session_id')
    if not campaign_id or not current_session_id:
        flash('No active session to wrap up.', 'warning')
        return redirect(url_for('session_mode.dashboard'))

    game_session = GameSession.query.filter_by(
        id=current_session_id, campaign_id=campaign_id
    ).first_or_404()

    return render_template(
        'session_mode/post_session.html',
        game_session=game_session,
    )


@session_mode_bp.route('/save-post-session', methods=['POST'])
@login_required
def save_post_session():
    """Process bulk updates from the post-session wrap-up form."""
    campaign_id = get_active_campaign_id()
    current_session_id = session.get('current_session_id')
    if not campaign_id or not current_session_id:
        return redirect(url_for('session_mode.dashboard'))

    game_session = GameSession.query.filter_by(
        id=current_session_id, campaign_id=campaign_id
    ).first_or_404()

    # Update session summary
    summary = request.form.get('summary', '').strip()
    if summary:
        game_session.summary = summary

    # Update quest statuses
    for quest in game_session.quests_touched:
        new_status = request.form.get(f'quest_status_{quest.id}')
        if new_status and new_status in ('active', 'completed', 'failed', 'on_hold'):
            quest.status = new_status

    # Update NPC statuses
    for npc in game_session.npcs_featured:
        new_status = request.form.get(f'npc_status_{npc.id}')
        if new_status and new_status in ('alive', 'dead', 'missing', 'unknown'):
            npc.status = new_status

    # Update item notes
    for item in game_session.items_mentioned:
        note = request.form.get(f'item_note_{item.id}', '').strip()
        if note:
            if item.description:
                item.description = item.description + '\n\n' + note
            else:
                item.description = note

    db.session.commit()

    # Clear session mode
    session.pop('in_session_mode', None)
    session.pop('current_session_id', None)
    session.pop('session_title', None)

    flash('Session wrapped up! All updates saved.', 'success')
    return redirect(url_for('sessions.session_detail', session_id=game_session.id))
