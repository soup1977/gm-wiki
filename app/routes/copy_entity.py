"""Copy Entity to Another Campaign — single shared Blueprint.

Provides a POST endpoint that duplicates any supported entity type
into a different campaign owned by the same user. Cross-campaign
foreign keys are nulled out; tags and images are duplicated.
"""
import os
import uuid
import shutil

from flask import Blueprint, redirect, url_for, request, flash, session as flask_session
from flask_login import login_required, current_user
from flask import current_app
from app import db
from app.models import (
    Campaign, NPC, Location, Quest, Item, Faction, CompendiumEntry,
    AdventureSite, RandomTable, TableRow, Encounter, EncounterMonster,
    ActivityLog, get_or_create_tags,
)

copy_entity_bp = Blueprint('copy_entity', __name__)


# ── Helpers ──────────────────────────────────────────────────────────────

def _duplicate_image(filename):
    """Copy an uploaded image file with a new UUID-based name. Returns new filename or None."""
    if not filename:
        return None
    upload_folder = current_app.config['UPLOAD_FOLDER']
    src_path = os.path.join(upload_folder, filename)
    if not os.path.exists(src_path):
        return None
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'png'
    new_filename = f"{uuid.uuid4().hex}.{ext}"
    shutil.copy2(src_path, os.path.join(upload_folder, new_filename))
    return new_filename


def _copy_tags(source_entity, target_campaign_id):
    """Recreate the source entity's tags in the target campaign."""
    if not hasattr(source_entity, 'tags') or not source_entity.tags:
        return []
    tag_string = ', '.join(t.name for t in source_entity.tags)
    return get_or_create_tags(target_campaign_id, tag_string)


# ── Per-type copier functions ────────────────────────────────────────────
# Each returns (new_entity, detail_url)

def _copy_npc(npc, target_cid):
    new = NPC(
        campaign_id=target_cid,
        name=npc.name + ' (copy)',
        role=npc.role,
        status=npc.status,
        faction=npc.faction,            # legacy text field
        physical_description=npc.physical_description,
        personality=npc.personality,
        secrets=npc.secrets,
        notes=npc.notes,
        is_player_visible=npc.is_player_visible,
        portrait_filename=_duplicate_image(npc.portrait_filename),
        # Cross-campaign FKs nulled:
        home_location_id=None,
        faction_id=None,
        story_arc_id=None,
    )
    db.session.add(new)
    db.session.flush()
    new.tags = _copy_tags(npc, target_cid)
    # connected_locations left empty (default)
    return new, url_for('npcs.npc_detail', npc_id=new.id)


def _copy_location(loc, target_cid):
    new = Location(
        campaign_id=target_cid,
        name=loc.name + ' (copy)',
        type=loc.type,
        description=loc.description,
        gm_notes=loc.gm_notes,
        notes=loc.notes,
        map_filename=_duplicate_image(loc.map_filename),
        is_player_visible=loc.is_player_visible,
        # Cross-campaign FKs nulled:
        parent_location_id=None,
        faction_id=None,
        story_arc_id=None,
    )
    db.session.add(new)
    db.session.flush()
    new.tags = _copy_tags(loc, target_cid)
    return new, url_for('locations.location_detail', location_id=new.id)


def _copy_quest(quest, target_cid):
    new = Quest(
        campaign_id=target_cid,
        name=quest.name + ' (copy)',
        status=quest.status,
        hook=quest.hook,
        description=quest.description,
        outcome=quest.outcome,
        gm_notes=quest.gm_notes,
        is_player_visible=quest.is_player_visible,
        # Cross-campaign FKs nulled:
        faction_id=None,
        story_arc_id=None,
    )
    db.session.add(new)
    db.session.flush()
    new.tags = _copy_tags(quest, target_cid)
    # involved_npcs and involved_locations left empty
    return new, url_for('quests.quest_detail', quest_id=new.id)


def _copy_item(item, target_cid):
    new = Item(
        campaign_id=target_cid,
        name=item.name + ' (copy)',
        type=item.type,
        rarity=item.rarity,
        description=item.description,
        gm_notes=item.gm_notes,
        image_filename=_duplicate_image(item.image_filename),
        is_player_visible=item.is_player_visible,
        # Cross-campaign FKs nulled:
        owner_npc_id=None,
        origin_location_id=None,
        story_arc_id=None,
    )
    db.session.add(new)
    db.session.flush()
    new.tags = _copy_tags(item, target_cid)
    return new, url_for('items.item_detail', item_id=new.id)


def _copy_faction(faction, target_cid):
    new = Faction(
        campaign_id=target_cid,
        name=faction.name + ' (copy)',
        description=faction.description,
        disposition=faction.disposition,
        gm_notes=faction.gm_notes,
    )
    db.session.add(new)
    db.session.flush()
    return new, url_for('factions.faction_detail', faction_id=new.id)


def _copy_compendium(entry, target_cid):
    new = CompendiumEntry(
        campaign_id=target_cid,
        title=entry.title + ' (copy)',
        category=entry.category,
        content=entry.content,
        is_gm_only=entry.is_gm_only,
    )
    db.session.add(new)
    db.session.flush()
    return new, url_for('compendium.entry_detail', entry_id=new.id)


def _copy_adventure_site(site, target_cid):
    new = AdventureSite(
        campaign_id=target_cid,
        name=site.name + ' (copy)',
        subtitle=site.subtitle,
        status=site.status,
        estimated_sessions=site.estimated_sessions,
        content=site.content,
        sort_order=site.sort_order,
        is_player_visible=site.is_player_visible,
        milestones=site.milestones,       # raw JSON string
        progress_pct=site.progress_pct,
    )
    db.session.add(new)
    db.session.flush()
    new.tags = _copy_tags(site, target_cid)
    # sessions left empty — those are campaign-specific
    return new, url_for('adventure_sites.site_detail', site_id=new.id)


def _copy_random_table(table, target_cid):
    new = RandomTable(
        campaign_id=target_cid,
        name=table.name + ' (copy)',
        category=table.category,
        description=table.description,
        is_builtin=False,   # copy is always a custom table
    )
    db.session.add(new)
    db.session.flush()
    # Clone child rows
    for row in table.rows:
        new_row = TableRow(
            table_id=new.id,
            content=row.content,
            weight=row.weight,
            display_order=row.display_order,
        )
        db.session.add(new_row)
    return new, url_for('tables.table_detail', table_id=new.id)


def _copy_encounter(enc, target_cid):
    new = Encounter(
        campaign_id=target_cid,
        name=enc.name + ' (copy)',
        encounter_type=enc.encounter_type,
        status='planned',          # reset status for the copy
        description=enc.description,
        gm_notes=enc.gm_notes,
        # Cross-campaign FKs nulled:
        session_id=None,
        loot_table_id=None,
        story_arc_id=None,
    )
    db.session.add(new)
    db.session.flush()
    # Clone monster slots — bestiary_entry_id is global (safe)
    for em in enc.monsters:
        new_em = EncounterMonster(
            encounter_id=new.id,
            bestiary_entry_id=em.bestiary_entry_id,
            count=em.count,
            notes=em.notes,
        )
        db.session.add(new_em)
    return new, url_for('encounters.encounter_detail', encounter_id=new.id)


# ── Dispatch table ───────────────────────────────────────────────────────

COPIER_MAP = {
    'npc':            ('NPC',            NPC,            _copy_npc),
    'location':       ('Location',       Location,       _copy_location),
    'quest':          ('Quest',          Quest,          _copy_quest),
    'item':           ('Item',           Item,           _copy_item),
    'faction':        ('Faction',        Faction,        _copy_faction),
    'compendium':     ('Compendium',     CompendiumEntry, _copy_compendium),
    'adventure_site': ('Story Arc',      AdventureSite,  _copy_adventure_site),
    'random_table':   ('Random Table',   RandomTable,    _copy_random_table),
    'encounter':      ('Encounter',      Encounter,      _copy_encounter),
}


# ── Main route ───────────────────────────────────────────────────────────

@copy_entity_bp.route('/copy-entity/<entity_type>/<int:entity_id>', methods=['POST'])
@login_required
def copy_entity(entity_type, entity_id):
    """Copy an entity to another campaign owned by the current user."""

    if entity_type not in COPIER_MAP:
        flash('Unknown entity type.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    display_name, model_cls, copier_fn = COPIER_MAP[entity_type]

    # Load source entity
    source = model_cls.query.get_or_404(entity_id)

    # Verify the user owns the source campaign
    source_campaign = Campaign.query.filter_by(
        id=source.campaign_id, user_id=current_user.id
    ).first()
    if not source_campaign:
        flash('Entity not found.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    # Validate target campaign
    target_campaign_id = request.form.get('target_campaign_id', type=int)
    if not target_campaign_id:
        flash('Please select a destination campaign.', 'warning')
        return redirect(request.referrer or url_for('main.index'))

    target_campaign = Campaign.query.filter_by(
        id=target_campaign_id, user_id=current_user.id
    ).first()
    if not target_campaign:
        flash('Destination campaign not found.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    if target_campaign_id == source.campaign_id:
        flash('Entity is already in that campaign.', 'warning')
        return redirect(request.referrer or url_for('main.index'))

    # Perform the copy
    try:
        new_entity, detail_url = copier_fn(source, target_campaign_id)
        db.session.commit()

        # Get display name for the new entity
        entity_display = getattr(new_entity, 'name', None) or getattr(new_entity, 'title', '')

        ActivityLog.log_event(
            'copied', entity_type, entity_display,
            entity_id=new_entity.id,
            campaign_id=target_campaign_id,
            details=f'From "{source_campaign.name}"',
        )

        # Switch active campaign to the target so the redirect works
        flask_session['active_campaign_id'] = target_campaign_id

        flash(
            f'{display_name} copied to "{target_campaign.name}". '
            f'Switched to that campaign.',
            'success'
        )
        return redirect(detail_url)

    except Exception as e:
        db.session.rollback()
        flash(f'Error copying {display_name.lower()}: {e}', 'danger')
        return redirect(request.referrer or url_for('main.index'))
