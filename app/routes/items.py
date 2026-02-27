from collections import defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Item, NPC, Location, Tag, item_tags, get_or_create_tags
from app.shortcode import process_shortcodes, clear_mentions, resolve_mentions_for_target

items_bp = Blueprint('items', __name__)

_ITEM_TEXT_FIELDS = ['description', 'gm_notes']

ITEM_RARITIES = ['common', 'uncommon', 'rare', 'very rare', 'legendary', 'unique']


def get_active_campaign_id():
    return session.get('active_campaign_id')


@items_bp.route('/items')
def list_items():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    session.pop('in_session_mode', None)
    session.pop('current_session_id', None)
    session.pop('session_title', None)

    active_tag = request.args.get('tag', '').strip().lower() or None
    query = Item.query.filter_by(campaign_id=campaign_id)
    if active_tag:
        query = query.join(Item.tags).filter(Tag.name == active_tag)
    items = query.order_by(Item.type, Item.name).all()

    all_tags = sorted(
        {tag for item in Item.query.filter_by(campaign_id=campaign_id).all() for tag in item.tags},
        key=lambda t: t.name
    )

    # Group by type
    groups = defaultdict(list)
    for item in items:
        key = item.type or 'Miscellaneous'
        groups[key].append(item)
    grouped_items = dict(sorted(groups.items()))

    return render_template('items/list.html', items=items, grouped_items=grouped_items,
                           all_tags=all_tags, active_tag=active_tag)


@items_bp.route('/items/new', methods=['GET', 'POST'])
def create_item():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Item name is required.', 'danger')
            return render_template('items/form.html', item=None,
                                   npcs=npcs, locations=locations,
                                   rarities=ITEM_RARITIES)

        owner_npc_id = request.form.get('owner_npc_id') or None
        origin_location_id = request.form.get('origin_location_id') or None

        item = Item(
            campaign_id=campaign_id,
            name=name,
            type=request.form.get('type', '').strip() or None,
            rarity=request.form.get('rarity', '').strip() or None,
            description=request.form.get('description', '').strip() or None,
            gm_notes=request.form.get('gm_notes', '').strip() or None,
            owner_npc_id=int(owner_npc_id) if owner_npc_id else None,
            origin_location_id=int(origin_location_id) if origin_location_id else None,
        )
        item.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))
        item.is_player_visible = 'is_player_visible' in request.form
        db.session.add(item)
        db.session.flush()

        for field in _ITEM_TEXT_FIELDS:
            val = getattr(item, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'item', item.id)
                setattr(item, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()
        flash(f'Item "{item.name}" created.', 'success')
        return redirect(url_for('items.item_detail', item_id=item.id))

    return render_template('items/form.html', item=None,
                           npcs=npcs, locations=locations,
                           rarities=ITEM_RARITIES)


@items_bp.route('/items/<int:item_id>')
def item_detail(item_id):
    campaign_id = get_active_campaign_id()
    item = Item.query.filter_by(id=item_id, campaign_id=campaign_id).first_or_404()

    if request.args.get('from') != 'session':
        session.pop('in_session_mode', None)
        session.pop('current_session_id', None)
        session.pop('session_title', None)

    mentions = resolve_mentions_for_target('item', item_id)
    return render_template('items/detail.html', item=item, mentions=mentions)


@items_bp.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_item(item_id):
    campaign_id = get_active_campaign_id()
    item = Item.query.filter_by(id=item_id, campaign_id=campaign_id).first_or_404()

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Item name is required.', 'danger')
            return render_template('items/form.html', item=item,
                                   npcs=npcs, locations=locations,
                                   rarities=ITEM_RARITIES)

        owner_npc_id = request.form.get('owner_npc_id') or None
        origin_location_id = request.form.get('origin_location_id') or None

        item.name = name
        item.type = request.form.get('type', '').strip() or None
        item.rarity = request.form.get('rarity', '').strip() or None
        item.description = request.form.get('description', '').strip() or None
        item.gm_notes = request.form.get('gm_notes', '').strip() or None
        item.owner_npc_id = int(owner_npc_id) if owner_npc_id else None
        item.origin_location_id = int(origin_location_id) if origin_location_id else None
        item.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))
        item.is_player_visible = 'is_player_visible' in request.form

        clear_mentions('item', item.id)
        for field in _ITEM_TEXT_FIELDS:
            val = getattr(item, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'item', item.id)
                setattr(item, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()
        flash(f'Item "{item.name}" updated.', 'success')
        return redirect(url_for('items.item_detail', item_id=item.id))

    return render_template('items/form.html', item=item,
                           npcs=npcs, locations=locations,
                           rarities=ITEM_RARITIES)


@items_bp.route('/items/<int:item_id>/delete', methods=['POST'])
def delete_item(item_id):
    campaign_id = get_active_campaign_id()
    item = Item.query.filter_by(id=item_id, campaign_id=campaign_id).first_or_404()
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f'Item "{name}" deleted.', 'success')
    return redirect(url_for('items.list_items'))
