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

    # Adventure Site linked to this session (first one, if any)
    active_site = (game_session.adventure_sites[0]
                   if game_session and game_session.adventure_sites else None)

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
        active_site=active_site,
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

    from app.ai_provider import is_ai_enabled
    return render_template(
        'session_mode/post_session.html',
        game_session=game_session,
        ai_enabled=is_ai_enabled(),
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

    # Check if the GM wants to start the next session
    if request.form.get('action') == 'next_session':
        session_id_to_carry = game_session.id
        # Clear session mode before redirecting
        session.pop('in_session_mode', None)
        session.pop('current_session_id', None)
        session.pop('session_title', None)
        return redirect(url_for('sessions.create_next_session', session_id=session_id_to_carry))

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



@session_mode_bp.route('/toggle-visibility', methods=['POST'])
@login_required
def toggle_visibility():
    """AJAX endpoint to flip is_player_visible on an entity linked to the current session."""
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400

    data = request.get_json(silent=True) or {}
    entity_type = data.get('type', '')
    entity_id = data.get('id')

    if not entity_type or not entity_id:
        return jsonify({'error': 'Missing type or id.'}), 400

    type_map = {
        'npc': NPC,
        'quest': Quest,
        'item': Item,
        'location': Location,
    }

    model = type_map.get(entity_type)
    if not model:
        return jsonify({'error': f'Unknown entity type: {entity_type}'}), 400

    entity = model.query.filter_by(id=entity_id, campaign_id=campaign_id).first()
    if not entity:
        return jsonify({'error': 'Entity not found.'}), 404

    entity.is_player_visible = not entity.is_player_visible
    db.session.commit()

    return jsonify({
        'visible': entity.is_player_visible,
        'name': getattr(entity, 'name', ''),
    })


@session_mode_bp.route('/improv-encounter', methods=['POST'])
@login_required
def improv_encounter():
    """Generate a quick on-the-fly combat encounter based on the current scene context."""
    from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider

    if not is_ai_enabled():
        return jsonify({'error': 'AI is not configured. Check Settings.'}), 403

    campaign_id = get_active_campaign_id()
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400

    data = request.get_json(silent=True) or {}
    location_name = (data.get('location_name') or 'unknown location').strip()
    party_size = int(data.get('party_size') or 4)

    campaign = Campaign.query.get(campaign_id)

    parts = [
        'You are a tabletop RPG encounter designer. Generate a quick, balanced combat encounter '
        'the GM can run immediately at the table with minimal prep. '
        'Format the output as Markdown with clear sections.'
    ]
    parts.append(f'Location: {location_name}')
    parts.append(f'Party size: {party_size} players')
    if campaign and campaign.ai_world_context:
        parts.append(f'World context: {campaign.ai_world_context}')
    parts.append(
        '\nProvide:\n'
        '- **Enemies:** Name, count, brief description\n'
        '- **Stats:** HP, ATK, any special ability (1 line each)\n'
        '- **Tactics:** 1-2 sentences on how they fight\n'
        '- **Loot:** One quick loot suggestion\n'
        'Keep it brief — the GM needs this fast, at the table.'
    )

    system_prompt = '\n\n'.join(parts)
    messages = [{'role': 'user', 'content': f'Generate an improv encounter for {location_name}.'}]

    try:
        response = ai_chat(system_prompt, messages, max_tokens=512,
                           provider=get_feature_provider('generate'))
        return jsonify({'encounter': response})
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 502


@session_mode_bp.route('/hazard-flavor', methods=['POST'])
@login_required
def hazard_flavor():
    """Generate vivid sensory flavor text for a hazard event."""
    from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider

    if not is_ai_enabled():
        return jsonify({'error': 'AI is not configured. Check Settings.'}), 403

    campaign_id = get_active_campaign_id()
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400

    data = request.get_json(silent=True) or {}
    hazard = (data.get('hazard') or '').strip()
    if not hazard:
        return jsonify({'error': 'Describe the hazard first.'}), 400

    campaign = Campaign.query.get(campaign_id)

    parts = [
        'You are a tabletop RPG narrator. Write vivid, sensory flavor text for a GM to read '
        'aloud when a hazard occurs at the table. '
        'Focus on what the players see, hear, smell, and feel. '
        'Keep it to 2-3 sentences — punchy and atmospheric, not a wall of text.'
    ]
    if campaign and campaign.ai_world_context:
        parts.append(f'World context: {campaign.ai_world_context}')

    system_prompt = '\n\n'.join(parts)
    messages = [{'role': 'user', 'content': f'Write flavor text for this hazard: {hazard}'}]

    try:
        response = ai_chat(system_prompt, messages, max_tokens=256,
                           provider=get_feature_provider('generate'))
        return jsonify({'flavor': response})
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 502


@session_mode_bp.route('/suggest-consequences', methods=['POST'])
@login_required
def suggest_consequences():
    """Suggest narrative ripple effects based on what happened this session."""
    from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider

    if not is_ai_enabled():
        return jsonify({'error': 'AI is not configured. Check Settings.'}), 403

    campaign_id = get_active_campaign_id()
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400

    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id required.'}), 400

    game_session = GameSession.query.filter_by(id=session_id, campaign_id=campaign_id).first()
    if not game_session:
        return jsonify({'error': 'Session not found.'}), 404

    campaign = Campaign.query.get(campaign_id)

    context_parts = []
    if game_session.summary:
        context_parts.append(f'Session summary:\n{game_session.summary[:2000]}')
    if game_session.gm_notes:
        context_parts.append(f'GM notes:\n{game_session.gm_notes[:1000]}')

    quest_lines = []
    for q in game_session.quests_touched:
        quest_lines.append(f'- {q.name} (status: {q.status})')
    if quest_lines:
        context_parts.append('Quest statuses:\n' + '\n'.join(quest_lines))

    npc_lines = []
    for n in game_session.npcs_featured:
        npc_lines.append(f'- {n.name} (status: {n.status})')
    if npc_lines:
        context_parts.append('NPC statuses:\n' + '\n'.join(npc_lines))

    if not context_parts:
        return jsonify({'error': 'Not enough session data to suggest consequences. Add a summary first.'}), 400

    system_prompt = (
        'You are a narrative consequence designer for tabletop RPGs. '
        'Based on what happened in the last session, suggest 3-5 ripple effects '
        'that could emerge in future sessions — new threats, changed relationships, '
        'opened opportunities, or lingering complications. '
        'Format as a Markdown bullet list. Each consequence should be 1-2 sentences. '
        'Be specific to the events described, not generic.'
    )
    if campaign and campaign.ai_world_context:
        system_prompt += f'\n\nWorld context: {campaign.ai_world_context}'

    user_content = '\n\n'.join(context_parts)
    messages = [{'role': 'user', 'content': user_content}]

    try:
        response = ai_chat(system_prompt, messages, max_tokens=512,
                           provider=get_feature_provider('generate'))
        return jsonify({'consequences': response})
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 502
