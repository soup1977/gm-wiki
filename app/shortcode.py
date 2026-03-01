"""Shortcode processor for inline entity linking.

Syntax: #type[Name]  e.g.  #loc[Loracos]  #npc[Marv]  #item[Sword of Destiny]

On save, each shortcode is:
  1. Looked up by name in the active campaign (case-insensitive).
  2. Created as a minimal stub if it doesn't exist (except PCs — lookup only).
  3. Replaced with a Markdown link: [Name](/entity/id)
  4. Recorded in EntityMention for back-reference display.
"""

import re
from flask import url_for

SHORTCODE_RE = re.compile(r'#(npc|loc|item|quest|comp|pc|site)\[([^\]]+)\]')

# Maps type prefix → model class name, name field, URL route, and route id param.
# Model classes are imported lazily inside functions to avoid circular imports.
TYPE_CONFIG = {
    'npc':   {
        'model':      'NPC',
        'name_field': 'name',
        'route':      'npcs.npc_detail',
        'id_param':   'npc_id',
        'label':      'NPC',
    },
    'loc':   {
        'model':      'Location',
        'name_field': 'name',
        'route':      'locations.location_detail',
        'id_param':   'location_id',
        'label':      'Location',
    },
    'item':  {
        'model':      'Item',
        'name_field': 'name',
        'route':      'items.item_detail',
        'id_param':   'item_id',
        'label':      'Item',
    },
    'quest': {
        'model':      'Quest',
        'name_field': 'name',
        'route':      'quests.quest_detail',
        'id_param':   'quest_id',
        'label':      'Quest',
    },
    'comp':  {
        'model':      'CompendiumEntry',
        'name_field': 'title',
        'route':      'compendium.entry_detail',
        'id_param':   'entry_id',
        'label':      'Compendium',
    },
    'pc':    {
        'model':      'PlayerCharacter',
        'name_field': 'character_name',
        'route':      'pcs.pc_detail',
        'id_param':   'pc_id',
        'label':      'PC',
    },
    'site':  {
        'model':      'AdventureSite',
        'name_field': 'name',
        'route':      'adventure_sites.site_detail',
        'id_param':   'site_id',
        'label':      'Adventure Site',
    },
}


def _get_model(model_name):
    """Import and return a model class by name (avoids circular imports)."""
    from app import models
    return getattr(models, model_name)


def _find_or_create_entity(type_key, name, campaign_id):
    """Return (entity, was_created) for the given type and name.

    Looks up case-insensitively. Creates a stub if not found (except PC).
    Returns (None, False) if type is 'pc' and not found.
    """
    from app import db

    cfg = TYPE_CONFIG[type_key]
    model_cls = _get_model(cfg['model'])
    name_col = getattr(model_cls, cfg['name_field'])

    # Case-insensitive lookup, scoped to campaign (PCs and campaign-scoped entities)
    if type_key == 'pc':
        entity = model_cls.query.filter(
            model_cls.campaign_id == campaign_id,
            name_col.ilike(name)
        ).first()
        return (entity, False)

    entity = model_cls.query.filter(
        model_cls.campaign_id == campaign_id,
        name_col.ilike(name)
    ).first()

    if entity:
        return (entity, False)

    # Create a minimal stub
    if type_key == 'quest':
        entity = model_cls(campaign_id=campaign_id, name=name, status='active')
    elif type_key == 'comp':
        entity = model_cls(campaign_id=campaign_id, title=name)
    else:
        entity = model_cls(campaign_id=campaign_id, **{cfg['name_field']: name})

    db.session.add(entity)
    db.session.flush()  # get the new ID immediately
    return (entity, True)


def _entity_url(type_key, entity_id):
    """Build the URL for a given entity type and ID."""
    cfg = TYPE_CONFIG[type_key]
    return url_for(cfg['route'], **{cfg['id_param']: entity_id})


def process_shortcodes(text, campaign_id, source_type, source_id):
    """Process all #type[Name] shortcodes in text.

    Returns (processed_text, list_of_EntityMention_objects).
    The caller is responsible for adding mentions to db.session and committing.
    """
    from app.models import EntityMention

    if not text:
        return (text, [])

    mentions = []
    seen_targets = set()  # deduplicate mentions within the same text

    def replace_match(m):
        type_key = m.group(1)
        name = m.group(2).strip()

        entity, _ = _find_or_create_entity(type_key, name, campaign_id)

        if entity is None:
            # PC not found — leave shortcode unchanged
            return m.group(0)

        link_url = _entity_url(type_key, entity.id)

        # Record back-reference (deduplicated)
        target_key = (type_key, entity.id)
        if target_key not in seen_targets:
            seen_targets.add(target_key)
            mention = EntityMention(
                campaign_id=campaign_id,
                source_type=source_type,
                source_id=source_id,
                target_type=type_key,
                target_id=entity.id,
            )
            mentions.append(mention)

        # Use the actual stored name (may differ in capitalisation)
        cfg = TYPE_CONFIG[type_key]
        display_name = getattr(entity, cfg['name_field'])
        return (f'<a href="{link_url}" class="shortcode-link"'
                f' data-preview-type="{type_key}"'
                f' data-preview-id="{entity.id}">{display_name}</a>')

    processed = SHORTCODE_RE.sub(replace_match, text)
    return (processed, mentions)


def clear_mentions(source_type, source_id):
    """Delete all EntityMention rows for a given source entity.

    Call this before reprocessing on edit, so removed shortcodes don't
    leave stale back-references.
    """
    from app import db
    from app.models import EntityMention
    EntityMention.query.filter_by(
        source_type=source_type,
        source_id=source_id
    ).delete()


def resolve_mentions_for_source(source_type, source_id):
    """Return a list of dicts describing entities that this source mentions (forward links).

    Each dict has: type, id, label, type_label, url
    Used by detail routes to populate a "Linked Entities" section.
    """
    from app.models import EntityMention

    raw = EntityMention.query.filter_by(
        source_type=source_type,
        source_id=source_id
    ).all()

    results = []
    for m in raw:
        cfg = TYPE_CONFIG.get(m.target_type)
        if not cfg:
            continue
        try:
            model_cls = _get_model(cfg['model'])
            entity = model_cls.query.get(m.target_id)
            if entity:
                display_name = getattr(entity, cfg['name_field'])
                url = _entity_url(m.target_type, m.target_id)
                results.append({
                    'type':       m.target_type,
                    'id':         m.target_id,
                    'label':      display_name,
                    'type_label': cfg['label'],
                    'url':        url,
                })
        except Exception:
            continue

    return results


def resolve_mentions_for_target(target_type, target_id):
    """Return a list of dicts describing entities that mention this target.

    Each dict has: type, id, label, url
    Used by detail routes to populate the "Referenced by" section.
    """
    from app.models import EntityMention

    raw = EntityMention.query.filter_by(
        target_type=target_type,
        target_id=target_id
    ).all()

    results = []
    for m in raw:
        cfg = TYPE_CONFIG.get(m.source_type)
        if not cfg:
            continue
        try:
            model_cls = _get_model(cfg['model'])
            entity = model_cls.query.get(m.source_id)
            if entity:
                display_name = getattr(entity, cfg['name_field'])
                url = _entity_url(m.source_type, m.source_id)
                results.append({
                    'type':  m.source_type,
                    'id':    m.source_id,
                    'label': f"{cfg['label']}: {display_name}",
                    'url':   url,
                })
        except Exception:
            continue  # skip if entity was deleted

    return results
