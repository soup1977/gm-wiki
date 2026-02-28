"""app/routes/campaign_assistant.py — AI Campaign Assistant

A multi-turn chat interface that is aware of the active campaign's content.
The GM can brainstorm ideas and ask the AI to generate entities (NPCs,
Locations, Quests, Items) which can be saved to the campaign with one click.

Routes:
  GET  /campaign-assistant              — chat page
  POST /api/ai/assistant                — chat API endpoint (multi-turn)
  POST /api/ai/assistant/save-entity   — create entity from AI JSON fields
  POST /api/ai/assistant/clear         — clear conversation history
"""

import json
import re

from flask import (
    Blueprint, render_template, request, jsonify,
    session as flask_session, current_app, url_for
)
from flask_login import login_required, current_user

from app import db
from app.models import Campaign, NPC, Location, Quest, Item
from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider

campaign_assistant_bp = Blueprint('campaign_assistant', __name__)

# --- Constants ---

HISTORY_KEY = 'assistant_history'
MAX_HISTORY_MESSAGES = 10   # Keep last 5 turns (user + assistant = 10 messages)

# Fields the AI should fill for each entity type — mirrors ai.py ENTITY_SCHEMAS
ENTITY_FIELDS = {
    'npc':      ['name', 'role', 'status', 'faction', 'physical_description',
                 'personality', 'secrets', 'notes'],
    'location': ['name', 'type', 'description', 'gm_notes', 'notes'],
    'quest':    ['name', 'status', 'hook', 'description', 'outcome', 'gm_notes'],
    'item':     ['name', 'type', 'rarity', 'description', 'gm_notes'],
}

# --- Helpers ---

def _get_active_campaign():
    """Return the active Campaign for the current user, or None."""
    campaign_id = flask_session.get('active_campaign_id')
    if campaign_id:
        return Campaign.query.filter_by(
            id=campaign_id, user_id=current_user.id
        ).first()
    return None


def _build_system_prompt(campaign):
    """Build the system prompt with campaign context and entity name lists."""
    lines = [
        "You are a creative assistant helping a Game Master build and run a tabletop RPG campaign.",
        "You help brainstorm story ideas, NPCs, locations, quests, items, and world-building details.",
        "",
        f"Campaign: {campaign.name}",
    ]
    if campaign.system:
        lines.append(f"System: {campaign.system}")
    if campaign.ai_world_context:
        lines.append(f"\nWorld context:\n{campaign.ai_world_context.strip()}")

    # Compact entity name lists so the AI can reference existing content
    npc_names = [r[0] for r in NPC.query
                 .filter_by(campaign_id=campaign.id)
                 .with_entities(NPC.name).limit(20).all()]
    loc_names = [r[0] for r in Location.query
                 .filter_by(campaign_id=campaign.id)
                 .with_entities(Location.name).limit(20).all()]
    quest_names = [r[0] for r in Quest.query
                   .filter_by(campaign_id=campaign.id)
                   .with_entities(Quest.name).limit(20).all()]

    if npc_names:
        lines.append(f"\nKnown NPCs: {', '.join(npc_names)}")
    if loc_names:
        lines.append(f"Known Locations: {', '.join(loc_names)}")
    if quest_names:
        lines.append(f"Known Quests: {', '.join(quest_names)}")

    lines += [
        "",
        "ENTITY CREATION FORMAT:",
        "When the user asks you to CREATE a specific entity (NPC, Location, Quest, or Item),",
        "include a structured JSON block at the END of your response using this format:",
        "",
        'To create an NPC:    [ENTITY:npc]{"name":"...","role":"...","status":"alive","faction":"","physical_description":"...","personality":"...","secrets":"...","notes":""}[/ENTITY]',
        'To create a Location: [ENTITY:location]{"name":"...","type":"...","description":"...","gm_notes":"...","notes":""}[/ENTITY]',
        'To create a Quest:   [ENTITY:quest]{"name":"...","status":"active","hook":"...","description":"...","outcome":"","gm_notes":""}[/ENTITY]',
        'To create an Item:   [ENTITY:item]{"name":"...","type":"...","rarity":"common","description":"...","gm_notes":""}[/ENTITY]',
        "",
        "Rules for entity blocks:",
        "- Only include entity blocks when explicitly asked to CREATE an entity.",
        "- For brainstorming or suggestions, use normal prose only — no entity blocks.",
        "- You may include multiple entity blocks in one response if asked for several entities.",
        "- The JSON inside the blocks must be valid. Use null for empty optional fields.",
        "- Valid status values for NPCs: alive, dead, unknown, missing",
        "- Valid rarity values for Items: common, uncommon, rare, very rare, legendary, unique",
        "- Valid status values for Quests: active, completed, failed, on_hold",
    ]

    return '\n'.join(lines)


def _parse_entities(text):
    """Extract [ENTITY:type]...[/ENTITY] blocks from AI response text.

    Returns (prose_text, list_of_entity_dicts) where prose_text has all
    entity blocks stripped out.
    """
    pattern = r'\[ENTITY:(\w+)\](.*?)\[/ENTITY\]'
    entities = []

    def _extract(m):
        entity_type = m.group(1).lower()
        json_str = m.group(2).strip()
        if entity_type in ENTITY_FIELDS:
            try:
                fields = json.loads(json_str)
                entities.append({'type': entity_type, 'fields': fields})
            except json.JSONDecodeError:
                pass  # Skip malformed blocks
        return ''

    prose = re.sub(pattern, _extract, text, flags=re.DOTALL).strip()
    return prose, entities


# --- Routes ---

@campaign_assistant_bp.route('/campaign-assistant')
@login_required
def chat():
    """Render the campaign assistant chat page."""
    campaign = _get_active_campaign()
    ai_enabled = is_ai_enabled()
    history = flask_session.get(HISTORY_KEY, [])

    # Entity counts for the context panel
    context = {}
    if campaign:
        context = {
            'npc_count': NPC.query.filter_by(campaign_id=campaign.id).count(),
            'location_count': Location.query.filter_by(campaign_id=campaign.id).count(),
            'quest_count': Quest.query.filter_by(campaign_id=campaign.id).count(),
            'item_count': Item.query.filter_by(campaign_id=campaign.id).count(),
        }

    return render_template(
        'campaign_assistant/chat.html',
        campaign=campaign,
        ai_enabled=ai_enabled,
        context=context,
        history=history,
    )


@campaign_assistant_bp.route('/api/ai/assistant', methods=['POST'])
@login_required
def send_message():
    """Accept a chat message, call the AI, return prose + any entity data."""
    if not is_ai_enabled():
        return jsonify({
            'error': 'AI is not configured. Go to Settings to set up a provider.'
        }), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'No message provided.'}), 400
    if len(message) > 4000:
        return jsonify({'error': 'Message too long (max 4000 characters).'}), 400

    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign. Select a campaign first.'}), 400

    system_prompt = _build_system_prompt(campaign)

    # Load conversation history and append the new user message
    history = flask_session.get(HISTORY_KEY, [])
    history.append({'role': 'user', 'content': message})

    # Trim to keep the context window manageable
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]

    try:
        raw_response = ai_chat(system_prompt, history, max_tokens=4096,
                               provider=get_feature_provider('assistant'))
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 500

    # Parse entity blocks out of the response
    prose, entities = _parse_entities(raw_response)

    # Store only the prose in history (entity blocks are handled by the UI)
    assistant_content = prose if prose else raw_response
    history.append({'role': 'assistant', 'content': assistant_content})
    flask_session[HISTORY_KEY] = history
    flask_session.modified = True

    return jsonify({
        'response': assistant_content,
        'entities': entities,
    })


@campaign_assistant_bp.route('/api/ai/assistant/save-entity', methods=['POST'])
@login_required
def save_entity():
    """Create a campaign entity from AI-generated JSON fields."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    entity_type = data.get('entity_type', '').lower()
    fields = data.get('fields', {})

    if entity_type not in ENTITY_FIELDS:
        return jsonify({'error': f'Unknown entity type: {entity_type}'}), 400

    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign selected.'}), 400

    try:
        if entity_type == 'npc':
            entity = NPC(
                campaign_id=campaign.id,
                name=fields.get('name') or 'Unnamed NPC',
                role=fields.get('role') or '',
                status=fields.get('status') or 'alive',
                faction=fields.get('faction') or '',
                physical_description=fields.get('physical_description') or '',
                personality=fields.get('personality') or '',
                secrets=fields.get('secrets') or '',
                notes=fields.get('notes') or '',
                is_player_visible=False,
            )
            db.session.add(entity)
            db.session.commit()
            view_url = url_for('npcs.npc_detail', npc_id=entity.id)

        elif entity_type == 'location':
            entity = Location(
                campaign_id=campaign.id,
                name=fields.get('name') or 'Unnamed Location',
                type=fields.get('type') or '',
                description=fields.get('description') or '',
                gm_notes=fields.get('gm_notes') or '',
                notes=fields.get('notes') or '',
                is_player_visible=False,
            )
            db.session.add(entity)
            db.session.commit()
            view_url = url_for('locations.location_detail', location_id=entity.id)

        elif entity_type == 'quest':
            entity = Quest(
                campaign_id=campaign.id,
                name=fields.get('name') or 'Unnamed Quest',
                status=fields.get('status') or 'active',
                hook=fields.get('hook') or '',
                description=fields.get('description') or '',
                outcome=fields.get('outcome') or '',
                gm_notes=fields.get('gm_notes') or '',
                is_player_visible=False,
            )
            db.session.add(entity)
            db.session.commit()
            view_url = url_for('quests.quest_detail', quest_id=entity.id)

        elif entity_type == 'item':
            valid_rarities = {'common', 'uncommon', 'rare', 'very rare', 'legendary', 'unique'}
            rarity = (fields.get('rarity') or 'common').lower()
            if rarity not in valid_rarities:
                rarity = 'common'
            entity = Item(
                campaign_id=campaign.id,
                name=fields.get('name') or 'Unnamed Item',
                type=fields.get('type') or '',
                rarity=rarity,
                description=fields.get('description') or '',
                gm_notes=fields.get('gm_notes') or '',
                is_player_visible=False,
            )
            db.session.add(entity)
            db.session.commit()
            view_url = url_for('items.item_detail', item_id=entity.id)

        return jsonify({'ok': True, 'url': view_url, 'name': entity.name})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'campaign_assistant save_entity error: {e}')
        return jsonify({'error': f'Failed to save: {str(e)}'}), 500


@campaign_assistant_bp.route('/api/ai/assistant/clear', methods=['POST'])
@login_required
def clear_history():
    """Clear the conversation history from the session."""
    flask_session.pop(HISTORY_KEY, None)
    flask_session.modified = True
    return jsonify({'ok': True})
