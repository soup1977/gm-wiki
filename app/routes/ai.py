"""
app/routes/ai.py — AI Smart Fill + Generate Entry endpoints

This Blueprint provides two JSON API endpoints:
  POST /api/ai/smart-fill      — extract fields from raw notes
  POST /api/ai/generate-entry  — create a complete entry from a concept prompt

If no AI provider is configured, both endpoints return a 403.
"""

import json
import re
from flask import Blueprint, request, jsonify, session as flask_session
from flask_login import login_required
from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider
from app.models import (ActivityLog, AppSetting, Adventure, AdventureRoom,
                        AdventureScene, RoomCreature, RoomLoot, RoomNPC,
                        NPC, Item, BestiaryEntry, ICRPGLootDef)

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


# ---------------------------------------------------------------------------
# Configurable token limits — reads from AppSetting, falls back to defaults
# ---------------------------------------------------------------------------

def _get_max_tokens(setting_key, default, multiplier=1.0):
    """Read a token limit from AppSetting, apply multiplier, clamp to range."""
    base = int(AppSetting.get(setting_key, str(default)))
    value = int(base * multiplier)
    return max(256, min(value, 16384))

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
            'content':  (
                'A focused Markdown overview of this story arc. '
                'Include: 2-3 key scenes or beats, the central conflict, major NPCs involved, '
                'a climax moment, and 2 possible outcomes. '
                'Use ## for section headings. Aim for 300-500 words — focused, not exhaustive.'
            ),
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


# ---------------------------------------------------------------------------
# Default AI prompts and editable prompt system
# ---------------------------------------------------------------------------

# These are the hardcoded defaults for all 6 AI prompts.
# Each prompt may contain {placeholder} tokens that get substituted at call time.
# Placeholders used:
#   {entity_type}   — entity type name in uppercase (smart_fill, generate)
#   {field_lines}   — field schema listing (smart_fill, generate)
#   {world_section} — world context block or empty string (generate, site_ideas, session_prep, draft_summary)
#
# GMs can override any prompt from Settings → AI Prompts.
# An empty override falls back to the hardcoded default.

DEFAULT_PROMPTS = {
    'smart_fill': """\
You are a helpful assistant for a tabletop RPG Game Master.
Your job is to read raw GM notes and extract structured data from them.

Extract the following fields for a {entity_type}:
{field_lines}

Rules:
- Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
- Use null for any field you cannot confidently determine from the text.
- For fields with specific allowed values (like status or rarity), only use those values.
- Do not invent information that isn't in the text.
- Keep field values as plain text (no Markdown formatting unless it's notes/description).
""",

    'generate': """\
You are a creative assistant for a tabletop RPG Game Master.
Your job is to invent a complete, detailed {entity_type} based on a short concept or idea.
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
""",

    'brainstorm_arcs': """\
You are a creative assistant for a tabletop RPG Game Master.
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
""",

    'site_ideas': """\
You are a creative assistant for a tabletop RPG Game Master.
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
""",

    'session_prep': """\
You are a GM prep assistant for a tabletop RPG.
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

Return a JSON object: {"prep_notes": "markdown string..."}
Return ONLY a valid JSON object. No explanation, no code fences.""",

    'draft_summary': """\
You are a session recap writer for a tabletop RPG.
Your job is to turn raw GM notes into a polished narrative summary suitable for players to read.
{world_section}
Guidelines:
- Write 2-4 paragraphs in narrative style, past tense
- Mention key NPCs, locations, and quest developments by name
- Write from a neutral narrator perspective
- Include dramatic moments and key decisions
- Do NOT include GM-only secrets or meta-game information
- Keep it concise -- this is a recap, not a novel chapter

Return a JSON object: {"summary": "markdown string..."}
Return ONLY a valid JSON object. No explanation, no code fences.""",

    'generate_arc_structure': """\
You are a creative assistant for a tabletop RPG Game Master.
Your job is to take a seed idea and design a complete Story Arc structure for a campaign.
{world_section}
Return a JSON object with these fields:
  "title": A short, evocative story arc title (5 words or fewer)
  "subtitle": A one-line tagline (e.g. "A web of merchant betrayal and bandit war")
  "premise": 2-3 sentences describing the arc's central conflict and what's at stake
  "hook": The inciting incident that draws the players in (1-2 sentences)
  "themes": Comma-separated themes (e.g. "betrayal, greed, unlikely alliances")
  "estimated_sessions": Rough session count as a string (e.g. "3-5")
  "milestones": A JSON array of 5-7 milestone strings — key narrative beats in order
               (e.g. ["Players learn of the merchant guild's secret", "The bandit army makes its first strike"])

Rules:
- Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
- Be creative but keep it grounded and immediately playable.
- The milestones should form a clear narrative arc from discovery to resolution.
- Match the tone of the campaign world context if provided.
""",

    'propose_arc_entities': """\
You are a creative assistant for a tabletop RPG Game Master.
Your job is to read a Story Arc description and propose the key NPCs, Locations, Quests, and Items \
that the GM will need to run it.

Propose ONLY what is narratively essential — not an exhaustive list. Aim for:
  - 3-5 NPCs (villain or antagonist, 1-2 allies or neutral contacts, 1-2 minor characters)
  - 2-4 Locations (primary location, 1-2 secondary locations)
  - 2-3 Quests (1 main quest, 1-2 side quests)
  - 1-2 Items (key McGuffin, reward, or plot item) — only if the arc naturally calls for them
  - 1-2 Encounters (combat or social) — only if the arc naturally calls for them

Return a JSON object:
{
  "npcs": [
    {"name": "...", "role": "villain|ally|neutral|minor", "description": "One sentence about who they are and their role in this arc."}
  ],
  "locations": [
    {"name": "...", "type": "city|dungeon|wilderness|building|etc", "description": "One sentence about this place and its significance."}
  ],
  "quests": [
    {"name": "...", "type": "main|side", "hook": "One sentence describing what draws the players into this quest."}
  ],
  "items": [
    {"name": "...", "description": "One sentence about this item and why it matters to the arc."}
  ],
  "encounters": [
    {"name": "...", "description": "One sentence describing this encounter and what makes it interesting."}
  ]
}

Rules:
- Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
- Keep descriptions SHORT — one sentence each. The GM will flesh them out.
- Every entity you propose should have a clear reason to exist in THIS specific arc.
- If the arc doesn't naturally call for items or encounters, return empty arrays for those.
""",

    'generate_adventure': """\
You are an expert tabletop RPG adventure designer.
Generate a structured adventure module from the GM's concept.

{world_context_line}

Creature stat instructions: {stat_instructions}

IMPORTANT JSON rules:
- Return ONLY the raw JSON object. No markdown, no code fences, no explanation.
- All string values must be on a single line — no literal newlines inside strings.
- Use a pipe character | to separate bullet points in gm_notes (e.g. "- Gate is locked | - Groaning sounds beyond | - Secret door behind tapestry").
- Apostrophes and quotes inside strings must be avoided or rephrased.

JSON structure:
{
  "title": "Adventure Title",
  "tagline": "One evocative sentence",
  "synopsis": "2-3 sentence GM overview",
  "hook": "How players get involved. 1-2 sentences.",
  "premise": "What is at stake. 1-2 sentences.",
  "acts": [
    {
      "number": 1,
      "title": "Act Title",
      "description": "1-2 sentence act overview",
      "scenes": [
        {
          "title": "Scene Location Name",
          "description": "1-2 sentence area description",
          "scene_type": "dungeon",
          "rooms": [
            {
              "key": "A1",
              "title": "Room Name",
              "read_aloud": "2 vivid sentences in present tense for players.",
              "gm_notes": "- First note | - Second note | - Third note",
              "creatures": [
                {
                  "name": "Creature Name",
                  "hearts": 1,
                  "effort_type": "WEAPON",
                  "special_move": "One sentence special ability",
                  "timer_rounds": null,
                  "hp": null,
                  "ac": null,
                  "cr": ""
                }
              ],
              "loot": [
                {
                  "name": "Item Name",
                  "description": "Brief description"
                }
              ],
              "hazards": []
            }
          ]
        }
      ]
    }
  ],
  "key_npcs": [
    {
      "name": "NPC Name",
      "role": "Villain",
      "notes": "1-2 sentence personality and motivation"
    }
  ],
  "factions": [
    {
      "name": "Faction Name",
      "disposition": "hostile",
      "notes": "1-2 sentence description"
    }
  ],
  "quests": [
    {
      "name": "Quest Title",
      "hook": "One sentence — how players get involved.",
      "scope": "adventure",
      "status": "Active"
    }
  ]
}

Scope guidelines:
- 2-3 acts total
- 1-2 scenes per act
- 3-5 rooms per scene
- read_aloud: 2-3 sentences
- gm_notes: 2-4 bullet points separated by |
- 0-2 creatures per room, 0-1 loot per room
- Include 2-4 key NPCs and 1-3 factions
- Include 2-4 quests: scope must be either "adventure" or "campaign"
""",

    'flesh_out_room': """\
You are an expert tabletop RPG adventure writer.
Expand the read-aloud text and GM notes for a keyed dungeon/adventure room.
Also suggest new creatures, loot, or key NPCs ONLY if the room clearly warrants them
and they are not already present.

Adventure context:
{adventure_ctx}

{stat_instructions}

Currently in this room:
- Creatures: {existing_creatures}
- Loot: {existing_loot}
- NPCs: {existing_npcs}

IMPORTANT JSON rules:
- Return ONLY the raw JSON object. No markdown, no code fences.
- All string values must be on a single line — no literal newlines.
- Use | to separate bullet points in gm_notes.
- Leave new_creatures/new_loot/new_npcs as empty arrays [] if room is already populated or suggestions don't fit.
- NPCs are named characters the players interact with (prisoners, merchants, informants, bosses with dialogue).
  Do NOT put combat monsters in new_npcs — those go in new_creatures.

Return:
{
  "read_aloud": "2-3 vivid sentences in present tense for the players.",
  "gm_notes": "- First GM note | - Second note | - Third note",
  "new_creatures": [],
  "new_loot": [],
  "new_npcs": []
}

If suggesting creatures, use this format per creature:
{ "name": "...", "hearts": 1, "effort_type": "WEAPON", "special_move": "...", "timer_rounds": null, "hp": null, "ac": null, "cr": null, "actions": null }

If suggesting loot, use: { "name": "...", "description": "..." }
If suggesting NPCs, use: { "name": "...", "role": "...", "notes": "..." }
""",

    'generate_scene_rooms': """\
You are an expert tabletop RPG adventure designer.
Generate 3-4 keyed rooms for a specific scene/area in an adventure.

Adventure context:
{adventure_ctx}

Scene: {scene_title}
{scene_description_line}

Creature stat instructions: {stat_instructions}

IMPORTANT JSON rules:
- Return ONLY the raw JSON object. No markdown, no code fences.
- All string values on a single line — no literal newlines.
- Use | to separate bullet points in gm_notes.

Return:
{
  "rooms": [
    {
      "key": "{key_prefix}1",
      "title": "Room Name",
      "read_aloud": "2 vivid sentences in present tense.",
      "gm_notes": "- First note | - Second note",
      "creatures": [
        {
          "name": "Creature Name",
          "hearts": 1,
          "effort_type": "WEAPON",
          "special_move": "One sentence",
          "timer_rounds": null,
          "hp": null,
          "ac": null,
          "cr": ""
        }
      ],
      "loot": [
        {
          "name": "Item Name",
          "description": "Brief description"
        }
      ]
    }
  ]
}

Generate 3-4 rooms. Keep read_aloud to 2 sentences max, gm_notes to 2-3 bullets, 0-2 creatures, 0-1 loot per room.
""",

    'generate_room_creatures': """\
You are an expert tabletop RPG monster designer.
Generate 1-2 appropriate creatures for a room in an adventure.

Adventure context:
{adventure_ctx}

{stat_instructions}

IMPORTANT JSON rules:
- Return ONLY the raw JSON object. No markdown, no code fences.
- All string values on a single line.

Return:
{
  "creatures": [
    {
      "name": "Creature Name",
      "hearts": 1,
      "effort_type": "WEAPON",
      "special_move": "One sentence special ability or attack",
      "timer_rounds": null,
      "hp": null,
      "ac": null,
      "cr": ""
    }
  ]
}
""",

    'generate_room_loot': """\
You are an expert tabletop RPG loot designer.
Generate 1-2 thematically appropriate loot items for a room in an adventure.

Adventure context:
{adventure_ctx}

IMPORTANT JSON rules:
- Return ONLY the raw JSON object. No markdown, no code fences.
- All string values on a single line.

Return:
{
  "loot": [
    {
      "name": "Item Name",
      "description": "Brief evocative description, 1 sentence."
    }
  ]
}
""",

    'brainstorm_adventure': """\
You are a creative tabletop RPG adventure designer helping a GM brainstorm.
Generate useful planning ideas for their adventure.

Adventure: {adventure_name}
{adventure_ctx}

{existing_notes_section}

Generate a focused brainstorm block covering:
- 2-3 plot complications or twists
- 1-2 NPC motivations or secrets worth developing
- 1-2 potential player choice points or moral dilemmas
- Any interesting thematic elements worth exploring

Format as clear Markdown with bold headers and bullet points.
Keep it concise and directly useful at the game table.
""",

    'npc_chat': """\
When the GM describes a situation, respond with 3-4 short lines of dialogue
that this character would say. Stay in character. Be concise — this is for
quick reference at the game table, not prose. Include mannerisms or speech
patterns that fit the personality. Each line should be a separate thing the
NPC might say, giving the GM options to choose from.
""",

    'hazard_flavor': """\
You are a tabletop RPG narrator. Write vivid, sensory flavor text for a GM to read
aloud when a hazard occurs at the table.
Focus on what the players see, hear, smell, and feel.
Keep it to 2-3 sentences — punchy and atmospheric, not a wall of text.
{world_context}
""",

    'suggest_consequences': """\
You are a narrative consequence designer for tabletop RPGs.
Based on what happened in the last session, suggest 3-5 ripple effects
that could emerge in future sessions — new threats, changed relationships,
opened opportunities, or lingering complications.
Format as a Markdown bullet list. Each consequence should be 1-2 sentences.
Be specific to the events described, not generic.
{world_context}
""",

    'suggest_milestones': """\
You are a tabletop RPG adventure designer.
Based on the adventure site content provided, suggest 5-7 key milestones or story beats
that could be tracked as progress checkpoints for this adventure.
Each milestone should represent a meaningful moment of completion or achievement —
clearing an area, defeating a boss, finding a key item, triggering a plot revelation, etc.
Format as a Markdown bullet list. Each milestone is one line, starting with a verb.
{world_context}
""",

    'import_table': """\
You extract rollable random tables from web page text.
Return ONLY valid JSON, no explanation, no markdown fences.
Format: {"name": "Table Name", "entries": ["entry 1", "entry 2", ...]}
- Each entry should be a short, self-contained result suitable for rolling.
- If entries have numbers (like "1. ...", "2. ..."), strip the numbers.
- If the page has multiple tables, pick the largest or most interesting one.
- If no table is found, return: {"error": "No rollable table found on this page."}
""",
}


def _get_system_prompt(key, **subs):
    """Return the system prompt for key, reading from AppSetting with fallback to DEFAULT_PROMPTS.

    Substitutes {placeholder} tokens in the template using the provided kwargs.
    An empty AppSetting value falls back to the hardcoded default.
    """
    from app.models import AppSetting
    template = AppSetting.get(f'ai_prompt_{key}') or DEFAULT_PROMPTS[key]
    for placeholder, value in subs.items():
        template = template.replace('{' + placeholder + '}', value or '')
    return template


def _build_prompt(entity_type, text):
    """Build the system prompt and messages list for a Smart Fill extraction."""
    schema = ENTITY_SCHEMAS.get(entity_type)
    if not schema:
        return None

    field_lines = '\n'.join(
        f'  "{k}": {v}'
        for k, v in schema['fields'].items()
    )

    system_prompt = _get_system_prompt('smart_fill',
        entity_type=entity_type.upper(),
        field_lines=field_lines,
    )

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
        raw = ai_chat(system_prompt, messages,
                      max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048, 0.5),
                      json_mode=True, provider=get_feature_provider('smart_fill'))
        result = _extract_json(raw)
        return jsonify(result)

    except json.JSONDecodeError as e:
        ActivityLog.log_event('error', 'ai_smart_fill', 'Smart Fill failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        ActivityLog.log_event('error', 'ai_smart_fill', 'Smart Fill failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Generate Entry — create a complete entry from a short concept prompt
# ---------------------------------------------------------------------------

def _build_generate_prompt(entity_type, concept, world_context=None, arc_context=None):
    """Build the system prompt and messages for creative entity generation."""
    schema = ENTITY_SCHEMAS.get(entity_type)
    if not schema:
        return None

    field_lines = '\n'.join(
        f'  "{k}": {v}'
        for k, v in schema['fields'].items()
    )

    # Build world section — campaign context + optional story arc context
    world_section = ''
    if world_context:
        world_section = (
            f"\nCampaign world context (use this to inform tone, setting, and details):\n{world_context}\n"
        )
    if arc_context:
        world_section += (
            f"\nStory Arc context (this entity belongs to this arc — keep it consistent):\n{arc_context}\n"
        )

    system_prompt = _get_system_prompt('generate',
        entity_type=entity_type.upper(),
        field_lines=field_lines,
        world_section=world_section,
    )

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
        max_out_tokens = _get_max_tokens('ai_max_tokens_generate', 2048, 4.0)
    elif entity_type == 'bestiary':
        concept_limit = 5000
        max_out_tokens = _get_max_tokens('ai_max_tokens_generate', 2048, 2.0)
    else:
        concept_limit = 2000
        max_out_tokens = _get_max_tokens('ai_max_tokens_generate', 2048)

    if len(concept) > concept_limit:
        return jsonify({'error': f'Concept is too long (max ~{concept_limit} characters).'}), 400

    world_context = _get_active_world_context()

    # If the caller passes a story_arc_id, inject that arc's name + premise as context
    arc_context = None
    story_arc_id = data.get('story_arc_id')
    if story_arc_id:
        from app.models import AdventureSite
        campaign = _get_active_campaign()
        if campaign:
            arc = AdventureSite.query.filter_by(id=int(story_arc_id), campaign_id=campaign.id).first()
            if arc:
                arc_parts = [f"Story Arc: {arc.name}"]
                if arc.subtitle:
                    arc_parts.append(f"Tagline: {arc.subtitle}")
                if arc.content:
                    # First ~500 chars of arc content gives the AI enough narrative context
                    arc_parts.append(f"Arc overview:\n{arc.content[:500]}")
                arc_context = '\n'.join(arc_parts)

    messages, system_prompt = _build_generate_prompt(entity_type, concept, world_context, arc_context)

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
        ActivityLog.log_event('error', 'ai_generate', 'Generate Entry failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        ActivityLog.log_event('error', 'ai_generate', 'Generate Entry failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
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

    system_prompt = _get_system_prompt('brainstorm_arcs')

    messages = [
        {'role': 'user', 'content': "Brainstorm story arc ideas for this campaign:\n\n" + '\n'.join(context_parts)}
    ]

    try:
        raw = ai_chat(system_prompt, messages,
                      max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048),
                      json_mode=True, provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        ActivityLog.log_event('error', 'ai_brainstorm', 'Brainstorm Arcs failed',
                              details=str(e)[:200], campaign_id=campaign.id, immediate=True)
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        ActivityLog.log_event('error', 'ai_brainstorm', 'Brainstorm Arcs failed',
                              details=str(e)[:200], campaign_id=campaign.id, immediate=True)
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Save site idea as Encounter entity (no extra AI call — uses the content
# already generated by /site-ideas)
# ---------------------------------------------------------------------------

@ai_bp.route('/save-idea-as-encounter', methods=['POST'])
@login_required
def save_idea_as_encounter():
    """Create an Encounter entity directly from a site idea heading + description."""
    from app.models import Encounter
    from app import db

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    name        = data.get('name', '').strip()
    description = data.get('description', '').strip()
    if not name:
        return jsonify({'error': 'name is required.'}), 400

    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign.'}), 400

    encounter = Encounter(
        campaign_id=campaign.id,
        name=name,
        description=description,
        encounter_type='other',
    )
    db.session.add(encounter)
    db.session.commit()
    ActivityLog.log_event('created', 'encounter', encounter.name, entity_id=encounter.id,
                          campaign_id=campaign.id, details='from site idea')

    return jsonify({
        'id':   encounter.id,
        'name': encounter.name,
        'url':  f'/encounters/{encounter.id}',
    }), 201


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

    system_prompt = _get_system_prompt('site_ideas', world_section=world_section)

    user_content = f"Adventure site: {site_name}\n\n"
    if content:
        user_content += f"Existing content:\n{content}\n\n"
    user_content += "Suggest 4-6 new areas or encounters for this site."

    messages = [{'role': 'user', 'content': user_content}]

    try:
        raw = ai_chat(system_prompt, messages,
                      max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048),
                      json_mode=True, provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        ActivityLog.log_event('error', 'ai_site_ideas', 'Site Ideas failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        ActivityLog.log_event('error', 'ai_site_ideas', 'Site Ideas failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
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

    system_prompt = _get_system_prompt('session_prep', world_section=world_section)

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
        raw = ai_chat(system_prompt, messages,
                      max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048),
                      json_mode=True, provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        ActivityLog.log_event('error', 'ai_session_prep', 'Session Prep failed',
                              details=str(e)[:200], campaign_id=campaign.id, immediate=True)
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        ActivityLog.log_event('error', 'ai_session_prep', 'Session Prep failed',
                              details=str(e)[:200], campaign_id=campaign.id, immediate=True)
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

    system_prompt = _get_system_prompt('draft_summary', world_section=world_section)

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
        raw = ai_chat(system_prompt, messages,
                      max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048),
                      json_mode=True, provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        ActivityLog.log_event('error', 'ai_draft_summary', 'Draft Summary failed',
                              details=str(e)[:200], campaign_id=campaign.id, immediate=True)
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        ActivityLog.log_event('error', 'ai_draft_summary', 'Draft Summary failed',
                              details=str(e)[:200], campaign_id=campaign.id, immediate=True)
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Generate Arc Structure — Phase 17 Genesis Wizard Step 1→2
# ---------------------------------------------------------------------------

@ai_bp.route('/generate-arc-structure', methods=['POST'])
@login_required
def generate_arc_structure():
    """
    Takes a seed idea (free text + optional guided fields) and returns a
    complete Story Arc structure: title, subtitle, premise, hook, themes,
    estimated_sessions, and milestones[].

    Accepts JSON body:
      { "seed_text": "...",          # free-text premise (required)
        "conflict": "...",           # optional guided field
        "villain": "...",            # optional guided field
        "location": "...",           # optional guided field
        "hook": "...",               # optional guided field
        "stakes": "..."              # optional guided field
      }
    """
    if not is_ai_enabled():
        return jsonify({'error': 'AI features are not configured. Go to Settings to set up a provider.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    seed_text = data.get('seed_text', '').strip()
    if not seed_text:
        return jsonify({'error': 'seed_text is required.'}), 400

    # Build user message — combine free text with any guided field answers
    parts = [f"Seed idea: {seed_text}"]
    for field, label in [
        ('conflict', 'Central conflict'),
        ('villain',  'Villain/antagonist'),
        ('location', 'Primary location'),
        ('hook',     'Player hook'),
        ('stakes',   'Stakes'),
    ]:
        value = data.get(field, '').strip()
        if value:
            parts.append(f"{label}: {value}")

    world_context = _get_active_world_context()
    world_section = f"\nCampaign world context:\n{world_context}\n" if world_context else ''

    system_prompt = _get_system_prompt('generate_arc_structure', world_section=world_section)

    messages = [{'role': 'user', 'content': '\n'.join(parts)}]

    try:
        raw = ai_chat(system_prompt, messages,
                      max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048),
                      json_mode=True, provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        ActivityLog.log_event('error', 'ai_arc_structure', 'Arc Structure failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        ActivityLog.log_event('error', 'ai_arc_structure', 'Arc Structure failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Propose Arc Entities — Phase 17 Genesis Wizard Step 2→3
# ---------------------------------------------------------------------------

@ai_bp.route('/propose-arc-entities', methods=['POST'])
@login_required
def propose_arc_entities():
    """
    Takes a Story Arc's content/premise and returns a proposed bundle of
    NPCs, Locations, Quests, Items, and Encounters to create.

    Accepts JSON body:
      { "arc_title":   "...",
        "arc_premise": "...",
        "arc_content": "..."   # full arc description (optional but helps)
      }
    """
    if not is_ai_enabled():
        return jsonify({'error': 'AI features are not configured. Go to Settings to set up a provider.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    arc_title   = data.get('arc_title', '').strip()
    arc_premise = data.get('arc_premise', '').strip()
    arc_content = data.get('arc_content', '').strip()

    if not arc_title and not arc_premise:
        return jsonify({'error': 'arc_title or arc_premise is required.'}), 400

    # Build the user message with as much arc context as available
    parts = []
    if arc_title:
        parts.append(f"Story Arc: {arc_title}")
    if arc_premise:
        parts.append(f"Premise: {arc_premise}")
    if arc_content:
        trimmed = arc_content[:2000]
        if len(arc_content) > 2000:
            trimmed += '\n[...truncated...]'
        parts.append(f"\nArc details:\n{trimmed}")

    world_context = _get_active_world_context()
    if world_context:
        parts.insert(0, f"Campaign world context: {world_context[:500]}")

    system_prompt = _get_system_prompt('propose_arc_entities')

    messages = [{'role': 'user', 'content': '\n'.join(parts) + '\n\nPropose the entities needed to run this arc.'}]

    try:
        raw = ai_chat(system_prompt, messages,
                      max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048, 1.5),
                      json_mode=True, provider=get_feature_provider('generate'))
        result = _extract_json(raw)
        return jsonify(result)
    except json.JSONDecodeError as e:
        ActivityLog.log_event('error', 'ai_propose_entities', 'Propose Entities failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        ActivityLog.log_event('error', 'ai_propose_entities', 'Propose Entities failed',
                              details=str(e)[:200], campaign_id=flask_session.get('active_campaign_id'), immediate=True)
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Genesis Create Entity — Phase 17: generate + save one entity in one shot
# ---------------------------------------------------------------------------

# Maps entity_type → (model class, valid schema fields, detail URL pattern)
_GENESIS_ENTITY_CONFIG = {
    'npc':       ('NPC',       ['name','role','status','faction','physical_description','personality','secrets','notes'],     '/npcs/{id}'),
    'location':  ('Location',  ['name','type','description','gm_notes','notes'],                                              '/locations/{id}'),
    'quest':     ('Quest',     ['name','status','hook','description','outcome','gm_notes'],                                   '/quests/{id}'),
    'item':      ('Item',      ['name','type','rarity','description','gm_notes'],                                             '/items/{id}'),
    'encounter': ('Encounter', ['name','encounter_type','description','gm_notes'],                                            '/encounters/{id}'),
}


@ai_bp.route('/genesis-create-entity', methods=['POST'])
@login_required
def genesis_create_entity():
    """
    Phase 17 Genesis Wizard — generates AND saves a single entity.
    Called once per entity in the Step 4 progress loop.

    Accepts JSON body:
      { "entity_type": "npc",
        "concept":     "A corrupt guild master who secretly funds bandits",
        "story_arc_id": 42
      }
    Returns JSON: { "id": 1, "name": "...", "entity_type": "npc", "url": "/npcs/1" }
    """
    if not is_ai_enabled():
        return jsonify({'error': 'AI features are not configured.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must be JSON.'}), 400

    entity_type   = data.get('entity_type', '').strip().lower()
    concept       = data.get('concept', '').strip()
    story_arc_id  = data.get('story_arc_id')

    if entity_type not in _GENESIS_ENTITY_CONFIG:
        return jsonify({'error': f'Unsupported entity type for genesis: {entity_type}'}), 400
    if not concept:
        return jsonify({'error': 'concept is required.'}), 400

    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign selected.'}), 400

    # Build arc context if story_arc_id was provided
    arc_context = None
    if story_arc_id:
        from app.models import AdventureSite
        arc = AdventureSite.query.filter_by(id=int(story_arc_id), campaign_id=campaign.id).first()
        if arc:
            arc_parts = [f"Story Arc: {arc.name}"]
            if arc.subtitle:
                arc_parts.append(f"Tagline: {arc.subtitle}")
            if arc.content:
                arc_parts.append(f"Arc overview:\n{arc.content[:500]}")
            arc_context = '\n'.join(arc_parts)

    world_context = _get_active_world_context()
    messages, system_prompt = _build_generate_prompt(entity_type, concept, world_context, arc_context)

    # Match the token limits used by the standard generate-entry endpoint
    mult = 2.0 if entity_type in ('location', 'npc') else 1.0
    gen_tokens = _get_max_tokens('ai_max_tokens_generate', 2048, mult)

    try:
        raw = ai_chat(system_prompt, messages, max_tokens=gen_tokens, json_mode=True,
                      provider=get_feature_provider('generate'))
        fields = _extract_json(raw)
    except json.JSONDecodeError as e:
        ActivityLog.log_event('error', 'ai_genesis', 'Genesis failed',
                              details=str(e)[:200], campaign_id=campaign.id, immediate=True)
        return jsonify({'error': f'AI parse error: {e.msg}'}), 500
    except AIProviderError as e:
        ActivityLog.log_event('error', 'ai_genesis', 'Genesis failed',
                              details=str(e)[:200], campaign_id=campaign.id, immediate=True)
        return jsonify({'error': str(e)}), 500

    # Resolve the model class and valid fields
    model_name, valid_fields, url_pattern = _GENESIS_ENTITY_CONFIG[entity_type]
    from app import models as app_models
    ModelClass = getattr(app_models, model_name)

    # Build kwargs from AI-returned fields (only those that exist on the model)
    kwargs = {'campaign_id': campaign.id}
    for field in valid_fields:
        value = fields.get(field)
        if value is not None and str(value).strip():
            kwargs[field] = str(value).strip() if not isinstance(value, bool) else value

    # Apply type-specific defaults
    if entity_type == 'npc' and 'status' not in kwargs:
        kwargs['status'] = 'alive'
    if entity_type == 'quest' and 'status' not in kwargs:
        kwargs['status'] = 'active'

    # Link to story arc
    if story_arc_id:
        kwargs['story_arc_id'] = int(story_arc_id)

    from app import db
    entity = ModelClass(**kwargs)
    db.session.add(entity)
    db.session.commit()
    ActivityLog.log_event('created', entity_type, entity.name, entity_id=entity.id,
                          campaign_id=campaign.id, details='AI genesis')

    return jsonify({
        'id':          entity.id,
        'name':        entity.name,
        'entity_type': entity_type,
        'url':         url_pattern.format(id=entity.id),
    }), 201


# ---------------------------------------------------------------------------
# Phase 20: Adventure Draft Generation
# ---------------------------------------------------------------------------

@ai_bp.route('/generate-adventure-draft', methods=['POST'])
@login_required
def generate_adventure_draft():
    """Generate a full adventure skeleton from a one-paragraph concept.

    Expects JSON: { concept, system_hint, world_context }
    Returns a structured adventure JSON ready for the draft review UI.
    """
    if not is_ai_enabled():
        return jsonify({'error': 'AI provider not configured'}), 403

    data = request.get_json() or {}
    concept = data.get('concept', '').strip()
    system_hint = data.get('system_hint', 'generic')
    world_context = data.get('world_context', '')

    if not concept:
        return jsonify({'error': 'No concept provided'}), 400

    # Build system_hint-specific instructions
    if system_hint == 'icrpg':
        stat_instructions = (
            "Use ICRPG stat blocks: hearts (integer, each heart = 10 HP), "
            "effort_type (one of: BASIC, WEAPON, MAGIC, ULTIMATE), "
            "special_move (one sentence), timer_rounds (optional integer for countdown timers). "
            "Do NOT use hp, ac, or cr fields."
        )
    elif system_hint == 'd20':
        stat_instructions = (
            "Use d20 stat blocks: hp (integer), ac (integer), cr (string like '1/4' or '5'), "
            "actions (free-text list of actions). "
            "Do NOT use hearts, effort_type, or timer_rounds fields."
        )
    else:
        stat_instructions = (
            "Use generic stat blocks: describe creatures briefly with hp and a special_move. "
            "Keep it system-agnostic."
        )

    world_context_line = f'Campaign world context: {world_context}' if world_context else ''
    system_prompt = _get_system_prompt('generate_adventure',
                                       stat_instructions=stat_instructions,
                                       world_context_line=world_context_line)

    messages = [{'role': 'user', 'content': f'Generate an adventure from this concept:\n\n{concept}'}]

    try:
        provider = get_feature_provider('generate')
        max_tokens = _get_max_tokens('ai_max_tokens_adventure', 8192)
        response = ai_chat(system_prompt, messages,
                           max_tokens=max_tokens,
                           json_mode=True,
                           provider=provider)

        adventure_data = _parse_ai_json(response)
        if adventure_data is None:
            return jsonify({'error': 'AI returned invalid JSON. Try again or simplify your concept.',
                            'raw': response[:300]}), 500

        # Inject system_hint so the draft review can use it
        adventure_data['system_hint'] = system_hint
        adventure_data['concept'] = concept

        return jsonify(adventure_data)

    except AIProviderError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


def _parse_ai_json(response):
    """Robustly parse a JSON response from an AI, handling common formatting issues."""
    if not response:
        return None

    # Strip markdown code fences if present
    text = response.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

    # Attempt 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract the outermost { ... } block
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Attempt 3: strip trailing incomplete content after the last complete top-level key
    # (handles truncated responses by removing the last incomplete key)
    try:
        # Find the last complete closing brace at the top level
        depth = 0
        last_good = -1
        for i, ch in enumerate(text):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    last_good = i
        if last_good > 0:
            return json.loads(text[:last_good + 1])
    except (json.JSONDecodeError, Exception):
        pass

    return None


# ---------------------------------------------------------------------------
# Phase 20c: Adventure AI endpoints
# ---------------------------------------------------------------------------

def _get_adventure_context(adventure):
    """Build a short context string from an adventure for AI prompts."""
    parts = []
    if adventure.synopsis:
        parts.append(f'Synopsis: {adventure.synopsis}')
    if adventure.hook:
        parts.append(f'Hook: {adventure.hook}')
    if adventure.premise:
        parts.append(f'Premise: {adventure.premise}')
    return '\n'.join(parts) if parts else 'No adventure context available.'


def _system_hint_instructions(system_hint):
    """Return creature stat instructions based on system hint."""
    if system_hint == 'icrpg':
        return (
            "Use ICRPG stat blocks: hearts (integer), effort_type (BASIC/WEAPON/MAGIC/ULTIMATE), "
            "special_move (one sentence), timer_rounds (optional int). Do NOT use hp, ac, cr."
        )
    elif system_hint == 'd20':
        return (
            "Use d20 stat blocks: hp (integer), ac (integer), cr (string), actions (text). "
            "Do NOT use hearts, effort_type, or timer_rounds."
        )
    return "Use generic stat blocks: hp (integer) and special_move (one sentence)."


@ai_bp.route('/flesh-out-room', methods=['POST'])
@login_required
def flesh_out_room():
    """Expand a room's read_aloud and gm_notes fields using AI.
    Optionally suggests new creatures, loot, and NPCs if the room warrants them.

    Expects JSON: { room_id }
    Returns JSON: { read_aloud, gm_notes, new_creatures[], new_loot[], new_npcs[] }
    """
    if not is_ai_enabled():
        return jsonify({'error': 'AI provider not configured'}), 403

    data = request.get_json() or {}
    room_id = data.get('room_id')
    if not room_id:
        return jsonify({'error': 'room_id required'}), 400

    room = AdventureRoom.query.get_or_404(room_id)
    adventure = room.scene.act.adventure

    adventure_ctx = _get_adventure_context(adventure)
    stat_instructions = _system_hint_instructions(adventure.system_hint or 'generic')

    # Describe what already exists so AI doesn't duplicate
    existing_creatures = ', '.join(c.name for c in room.creatures) if room.creatures else 'none'
    existing_loot = ', '.join(l.name for l in room.loot) if room.loot else 'none'
    existing_npcs = ', '.join(rn.npc.name for rn in room.room_npcs) if room.room_npcs else 'none'

    system_prompt = _get_system_prompt('flesh_out_room',
        adventure_ctx=adventure_ctx,
        stat_instructions=stat_instructions,
        existing_creatures=existing_creatures,
        existing_loot=existing_loot,
        existing_npcs=existing_npcs,
    )

    current_content = []
    if room.title:
        current_content.append(f'Room: {room.key} — {room.title}')
    if room.read_aloud:
        current_content.append(f'Current read-aloud: {room.read_aloud}')
    if room.gm_notes:
        current_content.append(f'Current GM notes: {room.gm_notes}')

    user_msg = '\n'.join(current_content) if current_content else f'Room key: {room.key}, Room title: {room.title or "Untitled"}'

    messages = [{'role': 'user', 'content': f'Flesh out this room:\n\n{user_msg}'}]

    try:
        provider = get_feature_provider('generate')
        response = ai_chat(system_prompt, messages,
                           max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048),
                           json_mode=True, provider=provider)
        result = _parse_ai_json(response)
        if result is None:
            return jsonify({'error': 'AI returned invalid JSON. Try again.', 'raw': response[:200]}), 500
        # Ensure arrays are present even if AI omitted them
        result.setdefault('new_creatures', [])
        result.setdefault('new_loot', [])
        result.setdefault('new_npcs', [])
        return jsonify(result)
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


@ai_bp.route('/apply-room-flesh-out/<int:room_id>', methods=['POST'])
@login_required
def apply_room_flesh_out(room_id):
    """Save AI flesh-out result to a room: updates text and optionally creates
    new creatures, loot items, and NPCs from the checked suggestions.

    Expects JSON: {
        read_aloud, gm_notes,
        new_creatures: [...],  # only the ones the GM checked
        new_loot: [...],
        new_npcs: [...]
    }
    """
    from app import db
    import traceback
    try:
        room = AdventureRoom.query.get_or_404(room_id)
        adventure = room.scene.act.adventure
        from app.models import Campaign
        campaign = Campaign.query.get(adventure.campaign_id)
        if campaign is None:
            return jsonify({'error': 'Adventure has no campaign attached.'}), 400
        data = request.get_json() or {}
    except Exception as e:
        return jsonify({'error': f'Setup error: {str(e)}', 'trace': traceback.format_exc()}), 500

    # Update text fields
    if 'read_aloud' in data:
        room.read_aloud = data['read_aloud']
    if 'gm_notes' in data:
        room.gm_notes = data['gm_notes']

    creatures_added = 0
    loot_added = 0
    npcs_added = 0

    try:
        # Create checked creatures
        for c_data in data.get('new_creatures', []):
            name = c_data.get('name', '').strip()
            if not name:
                continue
            creature = RoomCreature(
                room_id=room.id,
                name=name,
                hearts=c_data.get('hearts') or 1,
                effort_type=c_data.get('effort_type') or '',
                special_move=c_data.get('special_move') or '',
                timer_rounds=c_data.get('timer_rounds'),
                hp=c_data.get('hp'),
                ac=c_data.get('ac'),
                cr=c_data.get('cr') or '',
                actions=c_data.get('actions') or '',
            )
            # Bestiary lookup — case-insensitive name match
            bestiary_match = BestiaryEntry.query.filter(
                db.func.lower(BestiaryEntry.name) == name.lower()
            ).first()
            if bestiary_match:
                creature.bestiary_entry_id = bestiary_match.id
            db.session.add(creature)
            creatures_added += 1

        # Create checked loot
        for l_data in data.get('new_loot', []):
            name = l_data.get('name', '').strip()
            if not name:
                continue
            room_loot = RoomLoot(
                room_id=room.id,
                name=name,
                description=l_data.get('description') or '',
            )
            # Check ICRPGLootDef if ICRPG adventure
            if adventure.system_hint == 'icrpg':
                loot_def = ICRPGLootDef.query.filter(
                    db.func.lower(ICRPGLootDef.name) == name.lower()
                ).first()
                if loot_def:
                    room_loot.loot_def_id = loot_def.id
            db.session.add(room_loot)
            # Also create a campaign Item record linked to this adventure
            item = Item(
                campaign_id=campaign.id,
                name=name,
                type='loot',
                description=l_data.get('description') or '',
                adventure_id=adventure.id,
            )
            db.session.add(item)
            loot_added += 1

        # Create checked NPCs
        for n_data in data.get('new_npcs', []):
            name = n_data.get('name', '').strip()
            if not name:
                continue
            npc = NPC(
                campaign_id=campaign.id,
                name=name,
                role=n_data.get('role') or '',
                notes=n_data.get('notes') or '',
                adventure_id=adventure.id,
            )
            db.session.add(npc)
            db.session.flush()  # get npc.id before creating RoomNPC link
            room_link = RoomNPC(room_id=room.id, npc_id=npc.id)
            db.session.add(room_link)
            npcs_added += 1

        db.session.commit()
        return jsonify({'success': True, 'creatures_added': creatures_added,
                        'loot_added': loot_added, 'npcs_added': npcs_added})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@ai_bp.route('/generate-scene-rooms', methods=['POST'])
@login_required
def generate_scene_rooms():
    """Generate 3-4 keyed rooms for a scene and save them to the DB.

    Expects JSON: { scene_id }
    Returns JSON: { rooms: [...], count } with the newly-created room data.
    """
    from app import db
    if not is_ai_enabled():
        return jsonify({'error': 'AI provider not configured'}), 403

    data = request.get_json() or {}
    scene_id = data.get('scene_id')
    if not scene_id:
        return jsonify({'error': 'scene_id required'}), 400

    scene = AdventureScene.query.get_or_404(scene_id)
    adventure = scene.act.adventure
    adventure_ctx = _get_adventure_context(adventure)
    stat_instructions = _system_hint_instructions(adventure.system_hint or 'generic')

    # Find next available letter prefix for room keys
    existing_keys = set()
    for act in adventure.acts:
        for s in act.scenes:
            for r in s.rooms:
                if r.key:
                    existing_keys.add(r.key)

    used_prefixes = {k[0] for k in existing_keys if k}
    key_prefix = next((chr(c) for c in range(ord('A'), ord('Z') + 1) if chr(c) not in used_prefixes), 'X')

    scene_description_line = f'Scene description: {scene.description}' if scene.description else ''
    system_prompt = _get_system_prompt('generate_scene_rooms',
        adventure_ctx=adventure_ctx,
        stat_instructions=stat_instructions,
        scene_title=scene.title,
        scene_description_line=scene_description_line,
        key_prefix=key_prefix,
    )

    messages = [{'role': 'user', 'content': f'Generate rooms for the scene: {scene.title}'}]

    try:
        provider = get_feature_provider('generate')
        response = ai_chat(system_prompt, messages,
                           max_tokens=_get_max_tokens('ai_max_tokens_generate', 2048),
                           json_mode=True, provider=provider)
        result = _parse_ai_json(response)
        if result is None or 'rooms' not in result:
            return jsonify({'error': 'AI returned invalid JSON. Try again.', 'raw': response[:200]}), 500

        # Save rooms to DB
        created_rooms = []
        next_sort = max((r.sort_order or 0 for r in scene.rooms), default=0) + 1
        for room_data in result['rooms']:
            room = AdventureRoom(
                scene_id=scene.id,
                key=room_data.get('key', '?'),
                title=room_data.get('title', 'Untitled Room'),
                read_aloud=room_data.get('read_aloud', ''),
                gm_notes=room_data.get('gm_notes', ''),
                sort_order=next_sort,
            )
            db.session.add(room)
            db.session.flush()

            for c in room_data.get('creatures', []):
                creature = RoomCreature(
                    room_id=room.id,
                    name=c.get('name', 'Unknown'),
                    hearts=c.get('hearts'),
                    effort_type=c.get('effort_type'),
                    special_move=c.get('special_move'),
                    timer_rounds=c.get('timer_rounds'),
                    hp=c.get('hp'),
                    ac=c.get('ac'),
                    cr=c.get('cr'),
                )
                db.session.add(creature)

            for loot_data in room_data.get('loot', []):
                loot = RoomLoot(
                    room_id=room.id,
                    name=loot_data.get('name', 'Unknown'),
                    description=loot_data.get('description', ''),
                )
                db.session.add(loot)

            created_rooms.append({
                'id': room.id,
                'key': room.key,
                'title': room.title,
                'creature_count': len(room_data.get('creatures', [])),
                'loot_count': len(room_data.get('loot', [])),
            })
            next_sort += 1

        db.session.commit()
        return jsonify({'rooms': created_rooms, 'count': len(created_rooms)})

    except AIProviderError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


@ai_bp.route('/generate-room-creatures', methods=['POST'])
@login_required
def generate_room_creatures():
    """Generate 1-2 creatures appropriate for a room and save them to DB.

    Expects JSON: { room_id }
    Returns JSON: { creatures: [...], count }
    """
    from app import db
    if not is_ai_enabled():
        return jsonify({'error': 'AI provider not configured'}), 403

    data = request.get_json() or {}
    room_id = data.get('room_id')
    if not room_id:
        return jsonify({'error': 'room_id required'}), 400

    room = AdventureRoom.query.get_or_404(room_id)
    adventure = room.scene.act.adventure
    adventure_ctx = _get_adventure_context(adventure)
    stat_instructions = _system_hint_instructions(adventure.system_hint or 'generic')

    system_prompt = _get_system_prompt('generate_room_creatures',
        adventure_ctx=adventure_ctx,
        stat_instructions=stat_instructions,
    )

    room_desc = f'Room: {room.key} — {room.title or "Untitled"}'
    if room.gm_notes:
        room_desc += f'\nGM notes: {room.gm_notes}'

    messages = [{'role': 'user', 'content': f'Generate creatures for this room:\n\n{room_desc}'}]

    try:
        provider = get_feature_provider('generate')
        response = ai_chat(system_prompt, messages,
                           max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048),
                           json_mode=True, provider=provider)
        result = _parse_ai_json(response)
        if result is None or 'creatures' not in result:
            return jsonify({'error': 'AI returned invalid JSON. Try again.', 'raw': response[:200]}), 500

        created = []
        for c in result['creatures']:
            creature = RoomCreature(
                room_id=room.id,
                name=c.get('name', 'Unknown'),
                hearts=c.get('hearts'),
                effort_type=c.get('effort_type'),
                special_move=c.get('special_move'),
                timer_rounds=c.get('timer_rounds'),
                hp=c.get('hp'),
                ac=c.get('ac'),
                cr=c.get('cr'),
            )
            db.session.add(creature)
            db.session.flush()
            created.append({'id': creature.id, 'name': creature.name})

        db.session.commit()
        return jsonify({'creatures': created, 'count': len(created)})

    except AIProviderError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


@ai_bp.route('/generate-room-loot', methods=['POST'])
@login_required
def generate_room_loot():
    """Generate 1-2 thematically appropriate loot items for a room and save to DB.

    Expects JSON: { room_id }
    Returns JSON: { loot: [...], count }
    """
    from app import db
    if not is_ai_enabled():
        return jsonify({'error': 'AI provider not configured'}), 403

    data = request.get_json() or {}
    room_id = data.get('room_id')
    if not room_id:
        return jsonify({'error': 'room_id required'}), 400

    room = AdventureRoom.query.get_or_404(room_id)
    adventure = room.scene.act.adventure
    adventure_ctx = _get_adventure_context(adventure)

    system_prompt = _get_system_prompt('generate_room_loot',
        adventure_ctx=adventure_ctx,
    )

    room_desc = f'Room: {room.key} — {room.title or "Untitled"}'
    if room.gm_notes:
        room_desc += f'\nGM notes: {room.gm_notes}'

    messages = [{'role': 'user', 'content': f'Generate loot for this room:\n\n{room_desc}'}]

    try:
        provider = get_feature_provider('generate')
        response = ai_chat(system_prompt, messages,
                           max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048),
                           json_mode=True, provider=provider)
        result = _parse_ai_json(response)
        if result is None or 'loot' not in result:
            return jsonify({'error': 'AI returned invalid JSON. Try again.', 'raw': response[:200]}), 500

        created = []
        for loot_data in result['loot']:
            loot = RoomLoot(
                room_id=room.id,
                name=loot_data.get('name', 'Unknown'),
                description=loot_data.get('description', ''),
            )
            db.session.add(loot)
            db.session.flush()
            created.append({'id': loot.id, 'name': loot.name, 'description': loot.description})

        db.session.commit()
        return jsonify({'loot': created, 'count': len(created)})

    except AIProviderError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


@ai_bp.route('/brainstorm-adventure', methods=['POST'])
@login_required
def brainstorm_adventure():
    """Generate brainstorming ideas for an adventure's planning notes.

    Expects JSON: { adventure_id }
    Returns JSON: { text } — Markdown text to append to planning_notes.
    """
    if not is_ai_enabled():
        return jsonify({'error': 'AI provider not configured'}), 403

    data = request.get_json() or {}
    adventure_id = data.get('adventure_id')
    if not adventure_id:
        return jsonify({'error': 'adventure_id required'}), 400

    adventure = Adventure.query.get_or_404(adventure_id)
    adventure_ctx = _get_adventure_context(adventure)
    existing_notes = adventure.planning_notes or ''

    existing_notes_section = f'Existing planning notes (for context, do not repeat):\n{existing_notes[:500]}' if existing_notes else ''
    system_prompt = _get_system_prompt('brainstorm_adventure',
        adventure_name=adventure.name,
        adventure_ctx=adventure_ctx,
        existing_notes_section=existing_notes_section,
    )

    messages = [{'role': 'user', 'content': 'Generate brainstorming ideas for this adventure.'}]

    try:
        provider = get_feature_provider('generate')
        response = ai_chat(system_prompt, messages,
                           max_tokens=_get_max_tokens('ai_max_tokens_standard', 2048),
                           provider=provider)
        if not response:
            return jsonify({'error': 'AI returned empty response.'}), 500
        return jsonify({'text': response.strip()})

    except AIProviderError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500
