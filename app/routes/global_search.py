from flask import Blueprint, jsonify, request, session as flask_session, url_for
from flask_login import login_required, current_user
from app import db
from app.models import (
    NPC, Location, Quest, Session, Item, Faction, Encounter,
    PlayerCharacter, CompendiumEntry, BestiaryEntry, RandomTable,
    AdventureSite
)

global_search_bp = Blueprint('global_search', __name__, url_prefix='/api')

# Each entry: (Model, name_field, detail_endpoint, id_param, icon, campaign_scoped)
SEARCH_CONFIG = {
    'npc': (NPC, 'name', 'npcs.npc_detail', 'npc_id', 'bi-person', True),
    'location': (Location, 'name', 'locations.location_detail', 'location_id', 'bi-geo-alt', True),
    'quest': (Quest, 'name', 'quests.quest_detail', 'quest_id', 'bi-flag', True),
    'session': (Session, 'title', 'sessions.session_detail', 'session_id', 'bi-calendar-event', True),
    'item': (Item, 'name', 'items.item_detail', 'item_id', 'bi-backpack', True),
    'faction': (Faction, 'name', 'factions.faction_detail', 'faction_id', 'bi-shield', True),
    'encounter': (Encounter, 'name', 'encounters.encounter_detail', 'encounter_id', 'bi-map', True),
    'pc': (PlayerCharacter, 'character_name', 'pcs.pc_detail', 'pc_id', 'bi-person-badge', True),
    'compendium': (CompendiumEntry, 'title', 'compendium.entry_detail', 'entry_id', 'bi-journal-text', True),
    'bestiary': (BestiaryEntry, 'name', 'bestiary.entry_detail', 'entry_id', 'bi-collection', False),
    'table': (RandomTable, 'name', 'tables.table_detail', 'table_id', 'bi-dice-5', True),
    'adventure_site': (AdventureSite, 'name', 'adventure_sites.site_detail', 'site_id', 'bi-map', True),
}

# Human-readable labels for each entity type
TYPE_LABELS = {
    'npc': 'NPCs',
    'location': 'Locations',
    'quest': 'Quests',
    'session': 'Sessions',
    'item': 'Items',
    'faction': 'Factions',
    'encounter': 'Encounters',
    'pc': 'Player Characters',
    'compendium': 'Compendium',
    'bestiary': 'Bestiary',
    'table': 'Random Tables',
    'adventure_site': 'Adventure Sites',
}

# Player wiki mode only shows these types (no GM secrets)
PLAYER_WIKI_TYPES = {'npc', 'location', 'quest', 'faction', 'pc'}

# Wiki detail endpoints for player_wiki mode (type_key → (wiki_endpoint, wiki_id_param))
WIKI_ENDPOINTS = {
    'npc': ('wiki.wiki_npc_detail', 'npc_id'),
    'location': ('wiki.wiki_location_detail', 'location_id'),
    'quest': ('wiki.wiki_quest_detail', 'quest_id'),
    'item': ('wiki.wiki_item_detail', 'item_id'),
}


@global_search_bp.route('/global-search')
def global_search():
    q = request.args.get('q', '').strip()
    mode = request.args.get('mode', 'gm')

    if len(q) < 2:
        return jsonify({'groups': [], 'total': 0})

    # GM mode requires login
    if mode != 'player_wiki' and not current_user.is_authenticated:
        return jsonify({'groups': [], 'total': 0}), 401

    # Use campaign_id from session (GM mode) or query param (player wiki mode)
    campaign_id = flask_session.get('active_campaign_id')
    if not campaign_id and request.args.get('campaign_id'):
        try:
            campaign_id = int(request.args.get('campaign_id'))
        except (ValueError, TypeError):
            pass

    search_types = PLAYER_WIKI_TYPES if mode == 'player_wiki' else SEARCH_CONFIG.keys()
    groups = []
    total = 0

    for type_key in search_types:
        if type_key not in SEARCH_CONFIG:
            continue
        model, name_field, endpoint, id_param, icon, scoped = SEARCH_CONFIG[type_key]
        col = getattr(model, name_field)
        query = model.query.filter(col.ilike(f'%{q}%'))

        # Campaign scoping
        if scoped and campaign_id:
            query = query.filter(model.campaign_id == campaign_id)
        elif scoped and not campaign_id:
            continue  # skip campaign-scoped types if no active campaign

        # Player wiki: only show entities marked player-visible
        if mode == 'player_wiki':
            if hasattr(model, 'is_player_visible'):
                query = query.filter(model.is_player_visible == True)

        matches = query.limit(5).all()
        if not matches:
            continue

        group_results = []
        for item in matches:
            name = getattr(item, name_field)

            # Use wiki URLs for player_wiki mode
            if mode == 'player_wiki' and type_key in WIKI_ENDPOINTS:
                wiki_ep, wiki_id = WIKI_ENDPOINTS[type_key]
                url = url_for(wiki_ep, campaign_id=campaign_id, **{wiki_id: item.id})
            else:
                url = url_for(endpoint, **{id_param: item.id})

            # Build subtitle for extra context
            subtitle = ''
            if type_key == 'compendium' and hasattr(item, 'category') and item.category:
                subtitle = item.category
            elif type_key == 'bestiary' and hasattr(item, 'system') and item.system:
                subtitle = item.system
            elif type_key == 'npc' and hasattr(item, 'role') and item.role:
                subtitle = item.role
            elif type_key == 'session' and hasattr(item, 'number') and item.number:
                subtitle = f'Session {item.number}'
            elif type_key == 'adventure_site' and hasattr(item, 'status') and item.status:
                subtitle = item.status

            group_results.append({
                'name': name,
                'url': url,
                'subtitle': subtitle,
            })

        groups.append({
            'type': type_key,
            'label': TYPE_LABELS.get(type_key, type_key.replace('_', ' ').title()),
            'icon': icon,
            'results': group_results,
        })
        total += len(group_results)

        if total >= 20:
            break

    return jsonify({'groups': groups, 'total': total})
