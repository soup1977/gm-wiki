"""
app/routes/ai.py — AI Smart Fill endpoint

This Blueprint provides one JSON API endpoint:
  POST /api/ai/smart-fill

The client sends:
  { "entity_type": "npc", "text": "raw notes about the entity" }

The server asks Claude to extract structured fields and returns JSON:
  { "name": "...", "role": "...", ... }

If ANTHROPIC_API_KEY is not set, the endpoint returns a 403.
"""

import json
from flask import Blueprint, request, jsonify, current_app

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# ---------------------------------------------------------------------------
# Per-entity prompts and field schemas
# ---------------------------------------------------------------------------

# These tell Claude exactly what to extract and what valid values look like.
# The field descriptions help Claude make good guesses from ambiguous text.

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
    """Build the Claude messages list for a Smart Fill extraction."""
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

    return [
        {'role': 'user', 'content': f"Extract {entity_type} data from these notes:\n\n{text}"}
    ], system_prompt


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@ai_bp.route('/smart-fill', methods=['POST'])
def smart_fill():
    """
    Accepts JSON body: { "entity_type": "npc", "text": "..." }
    Returns JSON: { "name": "...", "role": "...", ... }
    """
    if not current_app.config.get('AI_ENABLED'):
        return jsonify({'error': 'AI features are not configured. Set ANTHROPIC_API_KEY in your environment.'}), 403

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
        import anthropic
        client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        raw = response.content[0].text.strip()

        # Strip markdown code fences if Claude added them despite instructions
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1]
            if raw.endswith('```'):
                raw = raw[:-3].strip()

        result = json.loads(raw)
        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({'error': 'Claude returned unexpected output. Try again.'}), 500
    except Exception as e:
        error_msg = str(e)
        if 'authentication' in error_msg.lower() or 'api_key' in error_msg.lower():
            return jsonify({'error': 'Invalid API key. Check your ANTHROPIC_API_KEY setting.'}), 403
        return jsonify({'error': f'AI request failed: {error_msg}'}), 500
