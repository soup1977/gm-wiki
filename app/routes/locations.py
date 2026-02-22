from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from app import db
from app.models import Location

locations_bp = Blueprint('locations', __name__, url_prefix='/locations')


def get_active_campaign_id():
    """Get the active campaign ID from session, or None."""
    return session.get('active_campaign_id')


@locations_bp.route('/')
def list_locations():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    return render_template('locations/list.html', locations=locations)


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

        location = Location(
            campaign_id=campaign_id,
            name=name,
            type=request.form.get('type', '').strip(),
            description=request.form.get('description', '').strip(),
            gm_notes=request.form.get('gm_notes', '').strip(),
            notes=request.form.get('notes', '').strip(),
            parent_location_id=parent_id
        )
        db.session.add(location)

        connected_ids = [int(i) for i in request.form.getlist('connected_location_ids')]
        location.connected_locations = Location.query.filter(Location.id.in_(connected_ids)).all()

        db.session.commit()

        flash(f'Location "{location.name}" created!', 'success')
        return redirect(url_for('locations.location_detail', location_id=location.id))

    # GET — show the form
    # Get all locations in this campaign for the parent dropdown
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    return render_template('locations/form.html', location=None, locations=locations)


@locations_bp.route('/<int:location_id>')
def location_detail(location_id):
    campaign_id = get_active_campaign_id()
    location = Location.query.get_or_404(location_id)

    # Ensure location belongs to the active campaign
    if location.campaign_id != campaign_id:
        flash('Location not found in this campaign.', 'danger')
        return redirect(url_for('locations.list_locations'))

    return render_template('locations/detail.html', location=location)


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

        connected_ids = [int(i) for i in request.form.getlist('connected_location_ids')]
        # Exclude self just in case
        location.connected_locations = Location.query.filter(
            Location.id.in_(connected_ids), Location.id != location.id
        ).all()

        db.session.commit()

        flash(f'Location "{location.name}" updated!', 'success')
        return redirect(url_for('locations.location_detail', location_id=location.id))

    # GET — show the form with current data
    # Exclude self from parent dropdown options
    locations = Location.query.filter_by(campaign_id=campaign_id).filter(
        Location.id != location.id
    ).order_by(Location.name).all()
    return render_template('locations/form.html', location=location, locations=locations)


@locations_bp.route('/<int:location_id>/delete', methods=['POST'])
def delete_location(location_id):
    campaign_id = get_active_campaign_id()
    location = Location.query.get_or_404(location_id)

    if location.campaign_id != campaign_id:
        flash('Location not found in this campaign.', 'danger')
        return redirect(url_for('locations.list_locations'))

    name = location.name
    db.session.delete(location)
    db.session.commit()

    flash(f'Location "{name}" deleted.', 'warning')
    return redirect(url_for('locations.list_locations'))
