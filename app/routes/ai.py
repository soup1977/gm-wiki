"""
app/routes/ai.py — AI Smart Fill + Generate Entry endpoints

This Blueprint provides two JSON API endpoints:
  POST /api/ai/smart-fill      — extract fields from raw notes
  POST /api/ai/generate-entry  — create a complete entry from a concept prompt

If no AI provider is configured, both endpoints return a 403.
"""

import json
from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# ---------------------------------------------------------------------------
# Per-entity prompts and field schemas
# ---------------------------------------------------------------------------

# These tell the AI exactly what to extract and what valid values look like.
# The field descriptions help the model make good guesses from ambiguous text.

ENTITY_SCHEMAS = {
    'npc': {
        'fields': {
            'name':                 'Full name of the NPC',
            'role':                 'Their job or role (e.g. "blacksmith", "merchant", "villain")',
            'status':               'One of: alive, dead, unknown, missing',
            'faction':              'Faction or group they belong to (leave blank if unknown)',
            'physical_description': 'What they look like — appearance, clothing, notable features',
            'personality':          'How they act, speak, their personality traits',
            'secrets':              'Hidden information the players don\'t know yet (GM only)',
            'notes':                'Any other relevant GM notes',
        },
    },
    'location': {
        'fields': {
            'name':        'Name of the location',
            'type':        'Type of place (e.g. "city", "dungeon", "tavern", "wilderness", "castle")',
            'description': 'What the location looks, feels, smells like — the atmosphere',
            'gm_notes':    'GM-only notes about secrets, encounters, or things to remember',
            'notes':       'General notes',
        },
    },
    'quest': {
        'fields': {
            'name':        'Short quest title or name',
            'status':      'One of: active, completed, failed, on_hold',
            'hook':        'How the party got involved — the inciting event',
            'description': 'Full quest description — what it involves, what\'s at stake',
            'outcome':     'What happened at the end (fill in if completed or failed)',
            'gm_notes':    'GM-only notes — secrets, planned twists, contingencies',
        },
    },
    'item': {
        'fields': {
            'name':        'Name of the item',
            'type':        'Item type (e.g. "weapon", "armor", "consumable", "artifact", "misc")',
            'rarity':      'One of: common, uncommon, rare, very rare, legendary, unique',
            'description': 'What it is, what it does, how it looks',
            'gm_notes':    'GM-only notes — true origin, hidden properties, plot relevance',
        },
    },
    'session': {
        'fields': {
            'number':    'Session number as an integer (e.g. 5). Return null if not mentioned.',
            'title':     'Short title for the session (e.g. "The Ambush at Miller\'s Crossing")',
            'summary':   'What happened this session — narrative recap',
            'gm_notes':  'GM-only notes — what went well, what to follow up on next time',
        },
    },
}


def _build_prompt(entity_type, text):
    """Build the system prompt and messages list for a Smart Fill extraction."""
    schema = ENTITY_SCHEMAS.get(entity_type)
    if not schema:
        return None

    field_lines = '\n'.join(
        f'  "{k}": {v}'
        for k, v in schema['fields'].items()
    )

    system_prompt = f"""You are a helpful assistant for a tabletop RPG Game Master.
Your job is to read raw GM notes and extract structured data from them.

Extract the following fields for a {entity_type.upper()}:
{field_lines}

Rules:
- Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
- Use null for any field you cannot confidently determine from the text.
- For fields with specific allowed values (like status or rarity), only use those values.
- Do not invent information that isn't in the text.
- Keep field values as plain text (no Markdown formatting unless it's notes/description).
"""

    messages = [
        {'role': 'user', 'content': f"Extract {entity_type} data from these notes:\n\n{text}"}
    ]

    return messages, system_prompt


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@ai_bp.route('/smart-fill', methods=['POST'])
@login_required
def smart_fill():
    """
    Accepts JSON body: { "entity_type": "npc", "text": "..." }
    Returns JSON: { "name": "...", "role": "...", ... }
    """
    if not is_ai_enabled():
        return jsonify({'error': 'AI features are not configured. Go to Settings to set up a provider.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    entity_type = data.get('entity_type', '').strip().lower()
    text = data.get('text', '').strip()

    if entity_type not in ENTITY_SCHEMAS:
        return jsonify({'error': f'Unknown entity type: {entity_type}'}), 400
    if not text:
        return jsonify({'error': 'No text provided.'}), 400
    if len(text) > 8000:
        return jsonify({'error': 'Text is too long (max ~8000 characters).'}), 400

    messages, system_prompt = _build_prompt(entity_type, text)

    try:
        raw = ai_chat(system_prompt, messages, max_tokens=1024, json_mode=True,
                      provider=get_feature_provider('smart_fill'))

        # Strip markdown code fences if the model added them despite instructions
        # (shouldn't happen with json_mode, but kept as a safety net for Anthropic)
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1]
            if raw.endswith('```'):
                raw = raw[:-3].strip()

        result = json.loads(raw)
        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({'error': 'AI returned unexpected output. Try again.'}), 500
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Generate Entry — create a complete entry from a short concept prompt
# ---------------------------------------------------------------------------

def _build_generate_prompt(entity_type, concept, world_context=None):
    """Build the system prompt and messages for creative entity generation."""
    schema = ENTITY_SCHEMAS.get(entity_type)
    if not schema:
        return None

    field_lines = '\n'.join(
        f'  "{k}": {v}'
        for k, v in schema['fields'].items()
    )

    # If the campaign has world context, inject it so AI output matches the setting
    world_section = ''
    if world_context:
        world_section = f"""
Campaign world context (use this to inform tone, setting, and details):
{world_context}
"""

    system_prompt = f"""You are a creative assistant for a tabletop RPG Game Master.
Your job is to invent a complete, detailed {entity_type.upper()} based on a short concept or idea.
{world_section}
Fill in ALL of the following fields:
{field_lines}

Rules:
- Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
- Be creative and detailed — flesh out every field with interesting, usable content.
- For fields with specific allowed values (like status or rarity), only use those values.
- Descriptions, notes, and personality fields should be 2-4 sentences minimum.
- Secrets and GM notes should contain plot hooks, hidden motivations, or things the players don't know.
- Keep the tone consistent with the campaign world context above, or dark/epic fantasy if none is provided.
- The result should be immediately usable in a game session with no editing needed.
"""

    messages = [
        {'role': 'user', 'content': f"Create a {entity_type} based on this concept:\n\n{concept}"}
    ]

    return messages, system_prompt


def _get_active_world_context():
    """Return the ai_world_context for the active campaign, or None."""
    from flask import session as flask_session
    from flask_login import current_user
    from app.models import Campaign
    campaign_id = flask_session.get('active_campaign_id')
    if campaign_id:
        campaign = Campaign.query.filter_by(
            id=campaign_id, user_id=current_user.id
        ).first()
        if campaign and campaign.ai_world_context:
            return campaign.ai_world_context.strip()
    return None


@ai_bp.route('/generate-prompt/<entity_type>')
@login_required
def get_generate_prompt(entity_type):
    """Return the default system prompt for a given entity type.
    Used by the shift+click prompt editor in ai_generate.js."""
    entity_type = entity_type.strip().lower()
    if entity_type not in ENTITY_SCHEMAS:
        return jsonify({'error': f'Unknown entity type: {entity_type}'}), 400
    world_context = _get_active_world_context()
    _, system_prompt = _build_generate_prompt(entity_type, '(concept placeholder)', world_context)
    return jsonify({'system_prompt': system_prompt})


@ai_bp.route('/generate-entry', methods=['POST'])
@login_required
def generate_entry():
    """
    Accepts JSON body: { "entity_type": "npc", "prompt": "a grizzled dwarven blacksmith" }
    Returns JSON: { "name": "...", "role": "...", ... }
    """
    if not is_ai_enabled():
        return jsonify({'error': 'AI features are not configured. Go to Settings to set up a provider.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    entity_type = data.get('entity_type', '').strip().lower()
    concept = data.get('prompt', '').strip()

    if entity_type not in ENTITY_SCHEMAS:
        return jsonify({'error': f'Unknown entity type: {entity_type}'}), 400
    if not concept:
        return jsonify({'error': 'No concept provided.'}), 400
    if len(concept) > 2000:
        return jsonify({'error': 'Concept is too long (max ~2000 characters).'}), 400

    world_context = _get_active_world_context()
    messages, system_prompt = _build_generate_prompt(entity_type, concept, world_context)

    # Allow optional custom system prompt override (from shift+click editor)
    custom_system = data.get('system_prompt', '').strip()
    if custom_system:
        system_prompt = custom_system

    try:
        raw = ai_chat(system_prompt, messages, max_tokens=2048, json_mode=True,
                      provider=get_feature_provider('generate'))

        # Strip markdown code fences if the model added them despite instructions
        # (shouldn't happen with json_mode, but kept as a safety net for Anthropic)
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1]
            if raw.endswith('```'):
                raw = raw[:-3].strip()

        result = json.loads(raw)
        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({'error': 'AI returned unexpected output. Try again.'}), 500
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 500
