"""
app/routes/ai.py — AI Smart Fill + Generate Entry endpoints

This Blueprint provides two JSON API endpoints:
  POST /api/ai/smart-fill      — extract fields from raw notes
  POST /api/ai/generate-entry  — create a complete entry from a concept prompt

If no AI provider is configured, both endpoints return a 403.
"""

import json
import re
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
    'faction': {
        'fields': {
            'name':        'Name of the faction or organization',
            'disposition': 'One of: friendly, neutral, hostile, unknown',
            'description': 'What this faction is, what they do, their goals and methods',
            'gm_notes':    'GM-only notes — secret agendas, internal conflicts, plot hooks',
        },
    },
    'adventure_site': {
        'fields': {
            'name':     'Name of the adventure site',
            'subtitle': 'A one-line tagline or description (e.g. "Flooded temple of a forgotten god")',
            'status':   'One of: Planned, Active, Completed',
            'content':  'Full Markdown content for the site — use ## headings for zones/areas, include encounters, traps, loot, NPCs',
        },
    },
    'bestiary': {
        'fields': {
            'name':       'Monster/creature name',
            'system':     'Game system (e.g. "D&D 5e", "ICRPG", "Pathfinder 2e")',
            'cr_level':   'Challenge rating or level (e.g. "CR 3", "Level 5")',
            'tags':       'Comma-separated tags (e.g. "undead, boss, cave")',
            'stat_block': 'Full stat block in Markdown — HP, AC, attacks, abilities, special traits. Format for readability.',
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
        result = _extract_json(raw)
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
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


def _get_active_campaign():
    """Return the active Campaign object, or None."""
    from flask import session as flask_session
    from flask_login import current_user
    from app.models import Campaign
    campaign_id = flask_session.get('active_campaign_id')
    if campaign_id:
        return Campaign.query.filter_by(
            id=campaign_id, user_id=current_user.id
        ).first()
    return None


def _extract_json(raw):
    """Robustly extract a JSON object from a model response.

    Anthropic models sometimes add a preamble ("Here is the data:") or wrap
    the JSON in code fences even when instructed not to. This function tries
    progressively looser extraction until it finds parseable JSON.

    Raises json.JSONDecodeError if no valid JSON object can be found.
    """
    raw = raw.strip()

    # 1. Try direct parse — works when the model behaves
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences (```json ... ``` or ``` ... ```)
    # Uses regex so it works even when there is leading text before the fence
    fence_match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', raw)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 2b. Code fence with no closing marker — response was truncated after JSON
    # Try parsing everything after the opening fence line
    open_fence = re.search(r'```(?:json)?\s*\n', raw)
    if open_fence:
        try:
            return json.loads(raw[open_fence.end():].strip())
        except json.JSONDecodeError:
            pass

    # 3. Find the first '{' and try to parse a JSON object from there
    brace_idx = raw.find('{')
    if brace_idx != -1:
        try:
            return json.loads(raw[brace_idx:])
        except json.JSONDecodeError:
            pass

    # Nothing worked — include a preview of the raw response in the error
    preview = raw[:300].replace('\n', ' ') if raw else '(empty response)'
    raise json.JSONDecodeError(
        f'No valid JSON found. Model returned: {preview}', raw, 0
    )


# Keep old name as an alias for callers that pass the raw string and expect
# a string back (they call json.loads themselves).
def _strip_code_fences(raw):
    """Legacy helper — prefer _extract_json for new code."""
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1]
        if raw.endswith('```'):
            raw = raw[:-3].strip()
    return raw


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

    # Adventure sites need very long responses (full Markdown doc inside JSON)
    # Bestiary needs moderate extra room for stat blocks
    if entity_type == 'adventure_site':
        concept_limit = 5000
        max_out_tokens = 8000   # near Haiku's 8192 ceiling
    elif entity_type == 'bestiary':
        concept_limit = 5000
        max_out_tokens = 4096
    else:
        concept_limit = 2000
        max_out_tokens = 2048

    if len(concept) > concept_limit:
        return jsonify({'error': f'Concept is too long (max ~{concept_limit} characters).'}), 400

    world_context = _get_active_world_context()
    messages, system_prompt = _build_generate_prompt(entity_type, concept, world_context)

    # Allow optional custom system prompt override (from shift+click editor)
    custom_system = data.get('system_prompt', '').strip()
    if custom_system:
        system_prompt = custom_system

    try:
        raw = ai_chat(system_prompt, messages, max_tokens=max_out_tokens, json_mode=True,
                      provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Brainstorm Arcs — generate story arc ideas from campaign context
# ---------------------------------------------------------------------------

@ai_bp.route('/brainstorm-arcs', methods=['POST'])
@login_required
def brainstorm_arcs():
    """Generate 3-5 story arc ideas based on campaign context."""
    if not is_ai_enabled():
        return jsonify({'error': 'AI features are not configured. Go to Settings to set up a provider.'}), 403

    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign selected.'}), 400

    from app.models import NPC, Location, Quest, Faction as FactionModel, AdventureSite
    npcs      = [n.name for n in NPC.query.filter_by(campaign_id=campaign.id).limit(20).all()]
    locations = [l.name for l in Location.query.filter_by(campaign_id=campaign.id).limit(20).all()]
    quests    = [q.name for q in Quest.query.filter_by(campaign_id=campaign.id).limit(20).all()]
    factions  = [f.name for f in FactionModel.query.filter_by(campaign_id=campaign.id).limit(20).all()]
    sites     = [s.name for s in AdventureSite.query.filter_by(campaign_id=campaign.id).limit(20).all()]

    context_parts = [f"Campaign: {campaign.name}"]
    if campaign.system:
        context_parts.append(f"System: {campaign.system}")
    if campaign.description:
        context_parts.append(f"Description: {campaign.description}")
    if campaign.ai_world_context:
        context_parts.append(f"World context: {campaign.ai_world_context}")
    if npcs:
        context_parts.append(f"Existing NPCs: {', '.join(npcs)}")
    if locations:
        context_parts.append(f"Existing locations: {', '.join(locations)}")
    if quests:
        context_parts.append(f"Existing quests: {', '.join(quests)}")
    if factions:
        context_parts.append(f"Existing factions: {', '.join(factions)}")
    if sites:
        context_parts.append(f"Existing adventure sites: {', '.join(sites)}")

    system_prompt = """You are a creative assistant for a tabletop RPG Game Master.
Your job is to brainstorm 3-5 story arc ideas based on the campaign context provided.

Each arc should:
- Build on existing NPCs, factions, locations, and quests when possible
- Be compelling, dramatic, and full of conflict
- Feel like a natural extension of what is already happening in the campaign
- Be different from each other -- offer variety in tone and scope

Return a JSON object with an "arcs" array. Each arc has:
  "title": Short, evocative arc name
  "hook": How the arc begins -- the inciting incident (1-2 sentences)
  "stakes": What is at risk if the players fail (1-2 sentences)
  "key_npcs": Comma-separated names of NPCs involved (existing or suggested new ones)
  "estimated_sessions": Rough number of sessions (e.g. "2-3" or "4-6")

Rules:
- Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
- Match the tone and setting of the campaign world context.
"""

    messages = [
        {'role': 'user', 'content': "Brainstorm story arc ideas for this campaign:\n\n" + '\n'.join(context_parts)}
    ]

    try:
        raw = ai_chat(system_prompt, messages, max_tokens=2048, json_mode=True,
                      provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Site Ideas -- generate room/encounter ideas for an adventure site
# ---------------------------------------------------------------------------

@ai_bp.route('/site-ideas', methods=['POST'])
@login_required
def site_ideas():
    """Generate 4-6 room/encounter/area ideas based on existing site content."""
    if not is_ai_enabled():
        return jsonify({'error': 'AI features are not configured. Go to Settings to set up a provider.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    site_name = data.get('name', '').strip()
    content   = data.get('content', '').strip()

    if not site_name:
        return jsonify({'error': 'Site name is required.'}), 400

    if len(content) > 4000:
        content = content[:4000] + '\n\n[...content truncated...]'

    world_context = _get_active_world_context()
    world_section = f"\nCampaign world context:\n{world_context}\n" if world_context else ''

    system_prompt = f"""You are a creative assistant for a tabletop RPG Game Master.
Your job is to suggest 4-6 new areas, rooms, or encounters for an adventure site.
{world_section}
Rules:
- Each idea should fit naturally with the existing content tone and setting.
- Offer variety -- mix combat encounters, puzzles, social interactions, exploration, and environmental hazards.
- Each idea should be a self-contained section a GM can drop into their adventure.
- Do NOT repeat areas that already exist in the content.

Return a JSON object with an "ideas" array. Each idea has:
  "heading": A short section heading (e.g. "The Flooded Archive")
  "description": 2-4 sentences describing the area -- what is there, what happens, what players find

Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
"""

    user_content = f"Adventure site: {site_name}\n\n"
    if content:
        user_content += f"Existing content:\n{content}\n\n"
    user_content += "Suggest 4-6 new areas or encounters for this site."

    messages = [{'role': 'user', 'content': user_content}]

    try:
        raw = ai_chat(system_prompt, messages, max_tokens=2048, json_mode=True,
                      provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Session Prep -- generate prep notes from site content + previous session
# ---------------------------------------------------------------------------

@ai_bp.route('/session-prep', methods=['POST'])
@login_required
def session_prep():
    """Generate session prep notes from linked adventure site, previous session, and entity context."""
    if not is_ai_enabled():
        return jsonify({'error': 'AI features are not configured. Go to Settings to set up a provider.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    from app.models import AdventureSite, Session as GameSession

    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign.'}), 400

    site_id        = data.get('site_id')
    session_number = data.get('session_number')
    npc_names      = data.get('npc_names', [])
    quest_names    = data.get('quest_names', [])

    site_content = ''
    site_name    = ''
    if site_id:
        site = AdventureSite.query.filter_by(id=int(site_id), campaign_id=campaign.id).first()
        if site:
            site_name    = site.name
            site_content = site.content or ''
            if len(site_content) > 4000:
                site_content = site_content[:4000] + '\n\n[...truncated...]'

    prev_summary = ''
    if session_number:
        try:
            prev_num = int(session_number) - 1
            if prev_num > 0:
                prev = GameSession.query.filter_by(
                    campaign_id=campaign.id, number=prev_num
                ).first()
                if prev and prev.summary:
                    prev_summary = prev.summary[:2000]
        except (ValueError, TypeError):
            pass

    world_context = _get_active_world_context()
    world_section = f"\nCampaign world context:\n{world_context}\n" if world_context else ''

    system_prompt = f"""You are a GM prep assistant for a tabletop RPG.
Your job is to write concise, actionable session prep notes a GM can reference during play.
{world_section}
The prep notes should include (as applicable):
- **Recap** -- 2-3 bullet points summarizing what happened last session
- **Key NPCs** -- Who might appear, their current motivations, what they want
- **Scenes and Encounters** -- Planned scenes based on the adventure site content
- **Open Threads** -- Active quests and loose ends to weave in
- **Decision Points** -- Moments where players might choose different paths
- **Sensory Details** -- A few evocative details to set the mood

Format as Markdown. Be concise. Use bullet points and bold headings.

Return a JSON object: {{"prep_notes": "markdown string..."}}
Return ONLY a valid JSON object. No explanation, no code fences."""

    parts = []
    if session_number:
        parts.append(f"Preparing for Session #{session_number}")
    if prev_summary:
        parts.append(f"\nPrevious session recap:\n{prev_summary}")
    if site_name:
        parts.append(f"\nAdventure site: {site_name}")
    if site_content:
        parts.append(f"\nSite content:\n{site_content}")
    if npc_names:
        parts.append(f"\nNPCs likely involved: {', '.join(npc_names)}")
    if quest_names:
        parts.append(f"\nActive quests: {', '.join(quest_names)}")

    if not parts:
        return jsonify({'error': 'Select an adventure site, NPCs, or quests to generate prep notes from.'}), 400

    messages = [{'role': 'user', 'content': '\n'.join(parts)}]

    try:
        raw = ai_chat(system_prompt, messages, max_tokens=2048, json_mode=True,
                      provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Draft Summary -- generate a session summary from GM notes and linked entities
# ---------------------------------------------------------------------------

@ai_bp.route('/draft-summary', methods=['POST'])
@login_required
def draft_summary():
    """Generate a narrative session summary from GM notes and linked entities."""
    if not is_ai_enabled():
        return jsonify({'error': 'AI features are not configured. Go to Settings to set up a provider.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    from app.models import Session as GameSession

    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign.'}), 400

    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'Session ID is required.'}), 400

    game_session = GameSession.query.filter_by(
        id=int(session_id), campaign_id=campaign.id
    ).first()
    if not game_session:
        return jsonify({'error': 'Session not found.'}), 404

    gm_notes   = game_session.gm_notes or ''
    prep_notes = game_session.prep_notes or ''

    npc_names      = [n.name for n in game_session.npcs_featured]
    quest_info     = [f"{q.name} ({q.status})" for q in game_session.quests_touched]
    location_names = [l.name for l in game_session.locations_visited]
    site_names     = [s.name for s in game_session.adventure_sites]

    if not gm_notes and not prep_notes:
        return jsonify({'error': 'No GM notes or prep notes to draft a summary from. Add some notes first.'}), 400

    world_context = _get_active_world_context()
    world_section = f"\nCampaign world context:\n{world_context}\n" if world_context else ''

    system_prompt = f"""You are a session recap writer for a tabletop RPG.
Your job is to turn raw GM notes into a polished narrative summary suitable for players to read.
{world_section}
Guidelines:
- Write 2-4 paragraphs in narrative style, past tense
- Mention key NPCs, locations, and quest developments by name
- Write from a neutral narrator perspective
- Include dramatic moments and key decisions
- Do NOT include GM-only secrets or meta-game information
- Keep it concise -- this is a recap, not a novel chapter

Return a JSON object: {{"summary": "markdown string..."}}
Return ONLY a valid JSON object. No explanation, no code fences."""

    parts = []
    title = ''
    if game_session.number:
        title += f"Session #{game_session.number}"
    if game_session.title:
        title += f" -- {game_session.title}" if title else game_session.title
    if title:
        parts.append(f"Session: {title}")
    if site_names:
        parts.append(f"Adventure site: {', '.join(site_names)}")
    if location_names:
        parts.append(f"Locations visited: {', '.join(location_names)}")
    if npc_names:
        parts.append(f"NPCs involved: {', '.join(npc_names)}")
    if quest_info:
        parts.append(f"Quests: {', '.join(quest_info)}")
    if prep_notes:
        parts.append(f"\nSession plan:\n{prep_notes[:2000]}")
    if gm_notes:
        parts.append(f"\nGM notes from play:\n{gm_notes[:3000]}")
    parts.append("\nWrite a narrative summary of this session based on the notes above.")

    messages = [{'role': 'user', 'content': '\n'.join(parts)}]

    try:
        raw = ai_chat(system_prompt, messages, max_tokens=2048, json_mode=True,
                      provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 500
