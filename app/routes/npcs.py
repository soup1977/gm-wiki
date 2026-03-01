from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required
from app import db, save_upload
from app.models import NPC, Location, Item, Tag, npc_tags, get_or_create_tags, Faction
from app.shortcode import process_shortcodes, clear_mentions, resolve_mentions_for_target

_NPC_TEXT_FIELDS = ['physical_description', 'personality', 'notes', 'secrets']

npcs_bp = Blueprint('npcs', __name__, url_prefix='/npcs')

NPC_STATUS_CHOICES = ['alive', 'dead', 'unknown', 'missing']


def get_active_campaign_id():
    """Get the active campaign ID from session, or None."""
    return session.get('active_campaign_id')


@npcs_bp.route('/')
@login_required
def list_npcs():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    session.pop('in_session_mode', None)
    session.pop('current_session_id', None)
    session.pop('session_title', None)

    active_tag = request.args.get('tag', '').strip().lower() or None
    query = NPC.query.filter_by(campaign_id=campaign_id)
    if active_tag:
        query = query.join(NPC.tags).filter(Tag.name == active_tag)
    npcs = query.order_by(NPC.name).all()

    all_tags = sorted(
        {tag for npc in NPC.query.filter_by(campaign_id=campaign_id).all() for tag in npc.tags},
        key=lambda t: t.name
    )
    return render_template('npcs/list.html', npcs=npcs, all_tags=all_tags, active_tag=active_tag)


@npcs_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_npc():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('NPC name is required.', 'danger')
            return redirect(url_for('npcs.create_npc'))

        home_id = request.form.get('home_location_id')
        home_id = int(home_id) if home_id else None

        faction_id_val = request.form.get('faction_id')
        faction_id = int(faction_id_val) if faction_id_val else None

        npc = NPC(
            campaign_id=campaign_id,
            name=name,
            role=request.form.get('role', '').strip(),
            status=request.form.get('status', 'alive'),
            faction_id=faction_id,
            physical_description=request.form.get('physical_description', '').strip(),
            personality=request.form.get('personality', '').strip(),
            secrets=request.form.get('secrets', '').strip(),
            notes=request.form.get('notes', '').strip(),
            home_location_id=home_id
        )
        db.session.add(npc)

        # getlist returns all selected values from a multi-select field
        connected_ids = [int(i) for i in request.form.getlist('connected_location_ids')]
        npc.connected_locations = Location.query.filter(Location.id.in_(connected_ids)).all()
        npc.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))

        portrait_file = request.files.get('portrait')
        filename = save_upload(portrait_file)
        if not filename:
            filename = request.form.get('sd_generated_filename', '').strip() or None
        if filename:
            npc.portrait_filename = filename

        npc.is_player_visible = 'is_player_visible' in request.form
        db.session.flush()  # get npc.id before processing shortcodes

        for field in _NPC_TEXT_FIELDS:
            val = getattr(npc, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'npc', npc.id)
                setattr(npc, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()

        flash(f'NPC "{npc.name}" created!', 'success')
        return redirect(url_for('npcs.npc_detail', npc_id=npc.id))

    # GET — show the form
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    factions = Faction.query.filter_by(campaign_id=campaign_id).order_by(Faction.name).all()
    return render_template('npcs/form.html', npc=None, locations=locations,
                           status_choices=NPC_STATUS_CHOICES, factions=factions)


@npcs_bp.route('/<int:npc_id>')
@login_required
def npc_detail(npc_id):
    campaign_id = get_active_campaign_id()
    npc = NPC.query.get_or_404(npc_id)

    if npc.campaign_id != campaign_id:
        flash('NPC not found in this campaign.', 'danger')
        return redirect(url_for('npcs.list_npcs'))

    if request.args.get('from') != 'session':
        session.pop('in_session_mode', None)
        session.pop('current_session_id', None)
        session.pop('session_title', None)

    mentions = resolve_mentions_for_target('npc', npc_id)
    return render_template('npcs/detail.html', npc=npc, mentions=mentions)


@npcs_bp.route('/<int:npc_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_npc(npc_id):
    campaign_id = get_active_campaign_id()
    npc = NPC.query.get_or_404(npc_id)

    if npc.campaign_id != campaign_id:
        flash('NPC not found in this campaign.', 'danger')
        return redirect(url_for('npcs.list_npcs'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('NPC name is required.', 'danger')
            return redirect(url_for('npcs.edit_npc', npc_id=npc.id))

        home_id = request.form.get('home_location_id')
        home_id = int(home_id) if home_id else None

        npc.name = name
        npc.role = request.form.get('role', '').strip()
        npc.status = request.form.get('status', 'alive')
        faction_id_val = request.form.get('faction_id')
        npc.faction_id = int(faction_id_val) if faction_id_val else None
        npc.physical_description = request.form.get('physical_description', '').strip()
        npc.personality = request.form.get('personality', '').strip()
        npc.secrets = request.form.get('secrets', '').strip()
        npc.notes = request.form.get('notes', '').strip()
        npc.home_location_id = home_id

        connected_ids = [int(i) for i in request.form.getlist('connected_location_ids')]
        npc.connected_locations = Location.query.filter(Location.id.in_(connected_ids)).all()
        npc.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))

        portrait_file = request.files.get('portrait')
        filename = save_upload(portrait_file)
        if not filename:
            filename = request.form.get('sd_generated_filename', '').strip() or None
        if filename:
            npc.portrait_filename = filename

        npc.is_player_visible = 'is_player_visible' in request.form

        clear_mentions('npc', npc.id)
        for field in _NPC_TEXT_FIELDS:
            val = getattr(npc, field)
            if val:
                processed, mentions = process_shortcodes(val, campaign_id, 'npc', npc.id)
                setattr(npc, field, processed)
                for m in mentions:
                    db.session.add(m)

        db.session.commit()

        flash(f'NPC "{npc.name}" updated!', 'success')
        return redirect(url_for('npcs.npc_detail', npc_id=npc.id))

    # GET — show the form with current data
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    factions = Faction.query.filter_by(campaign_id=campaign_id).order_by(Faction.name).all()
    return render_template('npcs/form.html', npc=npc, locations=locations,
                           status_choices=NPC_STATUS_CHOICES, factions=factions)


@npcs_bp.route('/<int:npc_id>/set-status', methods=['POST'])
@login_required
def set_npc_status(npc_id):
    campaign_id = get_active_campaign_id()
    npc = NPC.query.get_or_404(npc_id)
    if npc.campaign_id != campaign_id:
        flash('NPC not found in this campaign.', 'danger')
        return redirect(url_for('npcs.list_npcs'))
    new_status = request.form.get('status', '').strip()
    if new_status in NPC_STATUS_CHOICES:
        npc.status = new_status
        db.session.commit()
    return redirect(url_for('npcs.npc_detail', npc_id=npc_id))


@npcs_bp.route('/<int:npc_id>/delete', methods=['POST'])
@login_required
def delete_npc(npc_id):
    campaign_id = get_active_campaign_id()
    npc = NPC.query.get_or_404(npc_id)

    if npc.campaign_id != campaign_id:
        flash('NPC not found in this campaign.', 'danger')
        return redirect(url_for('npcs.list_npcs'))

    name = npc.name

    # Items owned by this NPC have a nullable FK — set to party-owned before deleting.
    for item in list(npc.items_owned):
        item.owner_npc_id = None

    # SQLAlchemy handles the many-to-many link tables (npc_location_link,
    # quest_npc_link, session_npc_link) automatically when the NPC is deleted.
    db.session.delete(npc)
    db.session.commit()

    flash(f'NPC "{name}" deleted.', 'warning')
    return redirect(url_for('npcs.list_npcs'))
