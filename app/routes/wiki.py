from flask import Blueprint, render_template, abort, request
from app.models import (
    Campaign, NPC, Location, Quest, Item, Session,
    CompendiumEntry, BestiaryEntry, PlayerCharacter,
    CampaignStatTemplate
)

wiki_bp = Blueprint('wiki', __name__, url_prefix='/wiki')


# ---------------------------------------------------------------------------
# Landing page — list all campaigns
# ---------------------------------------------------------------------------

@wiki_bp.route('/')
def wiki_index():
    campaigns = Campaign.query.order_by(Campaign.name).all()
    return render_template('wiki/index.html', campaigns=campaigns)


# ---------------------------------------------------------------------------
# Campaign home
# ---------------------------------------------------------------------------

@wiki_bp.route('/<int:campaign_id>/')
def campaign_home(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    active_quests = Quest.query.filter_by(
        campaign_id=campaign_id, is_player_visible=True, status='active'
    ).order_by(Quest.name).all()
    recent_sessions = Session.query.filter_by(
        campaign_id=campaign_id, is_player_visible=True
    ).order_by(Session.number.desc()).limit(3).all()
    return render_template(
        'wiki/campaign_home.html',
        campaign=campaign,
        active_quests=active_quests,
        recent_sessions=recent_sessions,
    )


# ---------------------------------------------------------------------------
# NPCs
# ---------------------------------------------------------------------------

@wiki_bp.route('/<int:campaign_id>/npcs')
def wiki_npcs(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    npcs = NPC.query.filter_by(
        campaign_id=campaign_id, is_player_visible=True
    ).order_by(NPC.name).all()
    return render_template('wiki/npcs/index.html', campaign=campaign, npcs=npcs)


@wiki_bp.route('/<int:campaign_id>/npcs/<int:npc_id>')
def wiki_npc_detail(campaign_id, npc_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    npc = NPC.query.filter_by(
        id=npc_id, campaign_id=campaign_id, is_player_visible=True
    ).first_or_404()
    return render_template('wiki/npcs/detail.html', campaign=campaign, npc=npc)


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

@wiki_bp.route('/<int:campaign_id>/locations')
def wiki_locations(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    locations = Location.query.filter_by(
        campaign_id=campaign_id, is_player_visible=True
    ).order_by(Location.name).all()
    return render_template(
        'wiki/locations/index.html', campaign=campaign, locations=locations
    )


@wiki_bp.route('/<int:campaign_id>/locations/<int:location_id>')
def wiki_location_detail(campaign_id, location_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    location = Location.query.filter_by(
        id=location_id, campaign_id=campaign_id, is_player_visible=True
    ).first_or_404()
    ancestors = []
    current = location.parent_location
    while current and len(ancestors) < 10:
        if current.is_player_visible:
            ancestors.append(current)
        current = current.parent_location
    ancestors.reverse()
    return render_template(
        'wiki/locations/detail.html', campaign=campaign, location=location,
        ancestors=ancestors
    )


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------

@wiki_bp.route('/<int:campaign_id>/quests')
def wiki_quests(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    quests = Quest.query.filter_by(
        campaign_id=campaign_id, is_player_visible=True
    ).order_by(Quest.name).all()
    return render_template('wiki/quests/index.html', campaign=campaign, quests=quests)


@wiki_bp.route('/<int:campaign_id>/quests/<int:quest_id>')
def wiki_quest_detail(campaign_id, quest_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    quest = Quest.query.filter_by(
        id=quest_id, campaign_id=campaign_id, is_player_visible=True
    ).first_or_404()
    return render_template(
        'wiki/quests/detail.html', campaign=campaign, quest=quest
    )


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@wiki_bp.route('/<int:campaign_id>/items')
def wiki_items(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    items = Item.query.filter_by(
        campaign_id=campaign_id, is_player_visible=True
    ).order_by(Item.name).all()
    return render_template('wiki/items/index.html', campaign=campaign, items=items)


@wiki_bp.route('/<int:campaign_id>/items/<int:item_id>')
def wiki_item_detail(campaign_id, item_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    item = Item.query.filter_by(
        id=item_id, campaign_id=campaign_id, is_player_visible=True
    ).first_or_404()
    return render_template('wiki/items/detail.html', campaign=campaign, item=item)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@wiki_bp.route('/<int:campaign_id>/sessions')
def wiki_sessions(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    sessions = Session.query.filter_by(
        campaign_id=campaign_id, is_player_visible=True
    ).order_by(Session.number.desc()).all()
    return render_template(
        'wiki/sessions/index.html', campaign=campaign, sessions=sessions
    )


@wiki_bp.route('/<int:campaign_id>/sessions/<int:session_id>')
def wiki_session_detail(campaign_id, session_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    sess = Session.query.filter_by(
        id=session_id, campaign_id=campaign_id, is_player_visible=True
    ).first_or_404()
    return render_template(
        'wiki/sessions/detail.html', campaign=campaign, sess=sess
    )


# ---------------------------------------------------------------------------
# Compendium
# ---------------------------------------------------------------------------

@wiki_bp.route('/<int:campaign_id>/compendium')
def wiki_compendium(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    all_entries = CompendiumEntry.query.filter_by(
        campaign_id=campaign_id, is_gm_only=False
    ).order_by(CompendiumEntry.category, CompendiumEntry.title).all()

    categories = sorted({e.category or 'Uncategorized' for e in all_entries})
    active_category = request.args.get('category', '').strip() or None

    if active_category:
        if active_category == 'Uncategorized':
            entries = [e for e in all_entries if not e.category]
        else:
            entries = [e for e in all_entries if e.category == active_category]
    else:
        entries = all_entries

    cat_counts = {}
    for e in all_entries:
        key = e.category or 'Uncategorized'
        cat_counts[key] = cat_counts.get(key, 0) + 1

    return render_template(
        'wiki/compendium/index.html', campaign=campaign, entries=entries,
        categories=categories, cat_counts=cat_counts,
        active_category=active_category
    )


@wiki_bp.route('/<int:campaign_id>/compendium/<int:entry_id>')
def wiki_compendium_detail(campaign_id, entry_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    entry = CompendiumEntry.query.filter_by(
        id=entry_id, campaign_id=campaign_id, is_gm_only=False
    ).first_or_404()
    return render_template(
        'wiki/compendium/detail.html', campaign=campaign, entry=entry
    )


# ---------------------------------------------------------------------------
# Bestiary (global — not campaign-scoped)
# ---------------------------------------------------------------------------

@wiki_bp.route('/<int:campaign_id>/bestiary')
def wiki_bestiary(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    entries = BestiaryEntry.query.filter_by(
        visible_to_players=True
    ).order_by(BestiaryEntry.name).all()
    return render_template(
        'wiki/bestiary/index.html', campaign=campaign, entries=entries
    )


@wiki_bp.route('/<int:campaign_id>/bestiary/<int:entry_id>')
def wiki_bestiary_detail(campaign_id, entry_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    entry = BestiaryEntry.query.filter_by(
        id=entry_id, visible_to_players=True
    ).first_or_404()
    return render_template(
        'wiki/bestiary/detail.html', campaign=campaign, entry=entry
    )


# ---------------------------------------------------------------------------
# Player Characters
# ---------------------------------------------------------------------------

@wiki_bp.route('/<int:campaign_id>/pcs')
def wiki_pcs(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    pcs = PlayerCharacter.query.filter_by(
        campaign_id=campaign_id
    ).order_by(PlayerCharacter.character_name).all()
    return render_template('wiki/pcs/index.html', campaign=campaign, pcs=pcs)


@wiki_bp.route('/<int:campaign_id>/pcs/<int:pc_id>')
def wiki_pc_detail(campaign_id, pc_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    pc = PlayerCharacter.query.filter_by(
        id=pc_id, campaign_id=campaign_id
    ).first_or_404()
    template_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()
    stat_lookup = {s.template_field_id: s.stat_value for s in pc.stats}
    stats_display = [
        (field.stat_name, stat_lookup.get(field.id, ''))
        for field in template_fields
    ]
    return render_template('wiki/pcs/detail.html', campaign=campaign,
                           pc=pc, stats_display=stats_display)
