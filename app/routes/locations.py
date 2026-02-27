from collections import defaultdict
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from app import db, save_upload
from app.models import Location, NPC, Item, Tag, location_tags, get_or_create_tags, Faction
from app.shortcode import process_shortcodes, clear_mentions, resolve_mentions_for_target

locations_bp = Blueprint('locations', __name__, url_prefix='/locations')

_LOC_TEXT_FIELDS = ['description', 'notes', 'gm_notes']


def get_active_campaign_id():
    """Get the active campaign ID from session, or None."""
    return session.get('active_campaign_id')


@locations_bp.route('/')
def list_locations():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    session.pop('in_session_mode', None)
    session.pop('current_session_id', None)
    session.pop('session_title', None)

    active_tag = request.args.get('tag', '').strip().lower() or None
    query = Location.query.filter_by(campaign_id=campaign_id)
    if active_tag:
        query = query.join(Location.tags).filter(Tag.name == active_tag)
    locations = query.order_by(Location.name).all()

    all_tags = sorted(
        {tag for loc in Location.query.filter_by(campaign_id=campaign_id).all() for tag in loc.tags},
        key=lambda t: t.name
    )

    # Group by parent location; "Top Level" group comes first
    groups = defaultdict(list)
    for loc in locations:
        key = loc.parent_location.name if loc.parent_location else 'Top Level'
        groups[key].append(loc)

    def group_sort_key(k):
        return (0, '') if k == 'Top Level' else (1, k.lower())

    grouped_locations = dict(sorted(groups.items(), key=lambda x: group_sort_key(x[0])))

    return render_template('locations/list.html', locations=locations,
                           grouped_locations=grouped_locations,
                           all_tags=all_tags, active_tag=active_tag)


@locations_bp.route('/new', methods=['GET', 'POST'])
def create_location():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Location name is required.', 'danger')
            return redirect(url_for('locations.create_location'))

        parent_id = request.form.get('parent_location_id')
        parent_id = int(parent_id) if parent_id else None

        faction_id_val = request.form.get('faction_id')
        faction_id = int(faction_id_val) if faction_id_val else None

        location = Location(
            campaign_id=campaign_id,
            name=name,
            type=request.form.get('type', '').strip(),
            description=request.form.get('description', '').strip(),
            gm_notes=request.form.get('gm_notes', '').strip(),
            notes=request.form.get('notes', '').strip(),
            parent_location_id=parent_id,
            faction_id=faction_id
        )
        db.session.add(location)

        connected_ids = [int(i) for i in request.form.getlist('connected_location_ids')]
        location.connected_locations = Location.query.filter(Location.id.in_(connected_ids)).all()
        location.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))

        map_file = request.files.get('map_image')
        filename = save_upload(map_file)
        if filename:
            location.map_filename = filename

        location.is_player_visible = 'is_player_visible' in request.form
        db.session.flush()

        for field in _LOC_TEXT_FIELDS:
            val = getattr(location, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'loc', location.id)
                setattr(location, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()

        flash(f'Location "{location.name}" created!', 'success')
        return redirect(url_for('locations.location_detail', location_id=location.id))

    # GET — show the form
    # Get all locations in this campaign for the parent dropdown
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    factions = Faction.query.filter_by(campaign_id=campaign_id).order_by(Faction.name).all()
    return render_template('locations/form.html', location=None, locations=locations, factions=factions)


@locations_bp.route('/<int:location_id>')
def location_detail(location_id):
    campaign_id = get_active_campaign_id()
    location = Location.query.get_or_404(location_id)

    # Ensure location belongs to the active campaign
    if location.campaign_id != campaign_id:
        flash('Location not found in this campaign.', 'danger')
        return redirect(url_for('locations.list_locations'))

    if request.args.get('from') != 'session':
        session.pop('in_session_mode', None)
        session.pop('current_session_id', None)
        session.pop('session_title', None)

    mentions = resolve_mentions_for_target('loc', location_id)
    return render_template('locations/detail.html', location=location, mentions=mentions)


@locations_bp.route('/<int:location_id>/edit', methods=['GET', 'POST'])
def edit_location(location_id):
    campaign_id = get_active_campaign_id()
    location = Location.query.get_or_404(location_id)

    if location.campaign_id != campaign_id:
        flash('Location not found in this campaign.', 'danger')
        return redirect(url_for('locations.list_locations'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Location name is required.', 'danger')
            return redirect(url_for('locations.edit_location', location_id=location.id))

        parent_id = request.form.get('parent_location_id')
        parent_id = int(parent_id) if parent_id else None

        # Prevent setting self as parent
        if parent_id == location.id:
            flash('A location cannot be its own parent.', 'danger')
            return redirect(url_for('locations.edit_location', location_id=location.id))

        location.name = name
        location.type = request.form.get('type', '').strip()
        location.description = request.form.get('description', '').strip()
        location.gm_notes = request.form.get('gm_notes', '').strip()
        location.notes = request.form.get('notes', '').strip()
        location.parent_location_id = parent_id
        faction_id_val = request.form.get('faction_id')
        location.faction_id = int(faction_id_val) if faction_id_val else None

        connected_ids = [int(i) for i in request.form.getlist('connected_location_ids')]
        # Exclude self just in case
        location.connected_locations = Location.query.filter(
            Location.id.in_(connected_ids), Location.id != location.id
        ).all()
        location.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))

        map_file = request.files.get('map_image')
        filename = save_upload(map_file)
        if filename:
            location.map_filename = filename

        location.is_player_visible = 'is_player_visible' in request.form

        clear_mentions('loc', location.id)
        for field in _LOC_TEXT_FIELDS:
            val = getattr(location, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'loc', location.id)
                setattr(location, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()

        flash(f'Location "{location.name}" updated!', 'success')
        return redirect(url_for('locations.location_detail', location_id=location.id))

    # GET — show the form with current data
    # Exclude self from parent dropdown options
    locations = Location.query.filter_by(campaign_id=campaign_id).filter(
        Location.id != location.id
    ).order_by(Location.name).all()
    factions = Faction.query.filter_by(campaign_id=campaign_id).order_by(Faction.name).all()
    return render_template('locations/form.html', location=location, locations=locations, factions=factions)


@locations_bp.route('/<int:location_id>/delete', methods=['POST'])
def delete_location(location_id):
    campaign_id = get_active_campaign_id()
    location = Location.query.get_or_404(location_id)

    if location.campaign_id != campaign_id:
        flash('Location not found in this campaign.', 'danger')
        return redirect(url_for('locations.list_locations'))

    name = location.name

    # Nullify nullable FKs that point to this location before deleting.
    # NPCs whose home is here — clear their home location.
    for npc in list(location.npcs_living_here):
        npc.home_location_id = None

    # Child locations (parent_location_id points here) — detach them.
    for child in list(location.child_locations):
        child.parent_location_id = None

    # Items that originated here — clear their origin.
    for item in list(location.items_found_here):
        item.origin_location_id = None

    # The self-referential location_connection table stores links in one direction.
    # Clear both sides explicitly so no orphaned rows remain.
    location.connected_locations = []
    location.connected_from = []

    # SQLAlchemy handles the many-to-many link tables (npc_location_link,
    # quest_location_link, session_location_link) automatically.
    db.session.delete(location)
    db.session.commit()

    flash(f'Location "{name}" deleted.', 'warning')
    return redirect(url_for('locations.list_locations'))
