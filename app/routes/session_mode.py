from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from flask_login import login_required
from app import db
from app.models import Session as GameSession, Quest, Location, Encounter, NPC, Item, Campaign

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

    # Providers available for the NPC chat toggle
    from app.ai_provider import get_available_providers, get_ai_config
    available_providers = get_available_providers()
    active_provider = get_ai_config()['provider']

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
        available_providers=available_providers,
        active_provider=active_provider,
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


@session_mode_bp.route('/npc-chat', methods=['POST'])
@login_required
def npc_chat():
    """Quick NPC dialogue generator — takes a situation and returns in-character lines."""
    from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider

    if not is_ai_enabled():
        return jsonify({'error': 'AI is not configured. Go to Settings to set up a provider.'}), 403

    campaign_id = get_active_campaign_id()
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400

    data = request.get_json(silent=True) or {}
    npc_id = data.get('npc_id')
    situation = (data.get('situation') or '').strip()
    requested_provider = data.get('provider')
    if requested_provider not in ('ollama', 'anthropic', None):
        requested_provider = None

    if not npc_id or not situation:
        return jsonify({'error': 'NPC and situation are required.'}), 400

    npc = NPC.query.filter_by(id=npc_id, campaign_id=campaign_id).first()
    if not npc:
        return jsonify({'error': 'NPC not found in this campaign.'}), 404

    # Build the character context from NPC data
    campaign = Campaign.query.get(campaign_id)
    current_session_id = session.get('current_session_id')
    game_session = GameSession.query.get(current_session_id) if current_session_id else None

    parts = [f'You are roleplaying as {npc.name}']
    if npc.role:
        parts[0] += f', a {npc.role}'
    parts[0] += ' in a tabletop RPG.'

    if npc.personality:
        parts.append(f'Personality: {npc.personality}')
    if npc.physical_description:
        parts.append(f'Physical appearance: {npc.physical_description}')
    if npc.faction_rel:
        faction_info = npc.faction_rel.name
        if npc.faction_rel.disposition:
            faction_info += f' ({npc.faction_rel.disposition})'
        parts.append(f'Faction: {faction_info}')
    if npc.secrets:
        parts.append(f'Secrets you know (use subtly, do not reveal directly): {npc.secrets}')
    if npc.notes:
        parts.append(f'Additional background: {npc.notes}')
    if game_session and game_session.active_location:
        parts.append(f'Current location: {game_session.active_location.name}')
    if campaign and campaign.ai_world_context:
        parts.append(f'World context: {campaign.ai_world_context}')

    parts.append(
        '\nWhen the GM describes a situation, respond with 3-4 short lines of dialogue '
        'that this character would say. Stay in character. Be concise — this is for '
        'quick reference at the game table, not prose. Include mannerisms or speech '
        'patterns that fit the personality. Each line should be a separate thing the '
        'NPC might say, giving the GM options to choose from.'
    )

    system_prompt = '\n\n'.join(parts)
    messages = [{'role': 'user', 'content': situation}]

    try:
        # Per-request toggle overrides the per-feature setting; falls back to feature setting
        effective_provider = requested_provider or get_feature_provider('npc_chat')
        response = ai_chat(system_prompt, messages, max_tokens=512, provider=effective_provider)
        return jsonify({'response': response})
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 502
