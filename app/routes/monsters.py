from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from app import db, save_upload
from app.models import MonsterInstance, BestiaryEntry, NPC, Session, Campaign, Location

monsters_bp = Blueprint('monsters', __name__,
                        url_prefix='/campaigns/<int:campaign_id>/monsters')

INSTANCE_STATUS_CHOICES = ['alive', 'dead', 'fled', 'unknown']


def _check_campaign(campaign_id):
    """Verify the campaign_id matches the active campaign. Return the campaign or None."""
    active_id = session.get('active_campaign_id')
    if active_id != campaign_id:
        flash('Monster Instances are only accessible for the active campaign.', 'warning')
        return None
    return Campaign.query.get_or_404(campaign_id)


@monsters_bp.route('/')
def list_instances(campaign_id):
    campaign = _check_campaign(campaign_id)
    if not campaign:
        return redirect(url_for('main.index'))

    status_filter = request.args.get('status', '').strip() or None
    entry_filter = request.args.get('entry_id', type=int)

    query = MonsterInstance.query.filter_by(campaign_id=campaign_id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if entry_filter:
        query = query.filter_by(bestiary_entry_id=entry_filter)

    instances = query.order_by(MonsterInstance.instance_name).all()

    # Build list of Bestiary Entries that have instances in this campaign (for filter dropdown)
    entry_ids = {i.bestiary_entry_id for i in
                 MonsterInstance.query.filter_by(campaign_id=campaign_id).all()}
    filter_entries = BestiaryEntry.query.filter(
        BestiaryEntry.id.in_(entry_ids)
    ).order_by(BestiaryEntry.name).all()

    return render_template('monsters/index.html', instances=instances,
                           campaign=campaign, status_choices=INSTANCE_STATUS_CHOICES,
                           status_filter=status_filter, entry_filter=entry_filter,
                           filter_entries=filter_entries)


@monsters_bp.route('/<int:instance_id>')
def instance_detail(campaign_id, instance_id):
    campaign = _check_campaign(campaign_id)
    if not campaign:
        return redirect(url_for('main.index'))

    instance = MonsterInstance.query.get_or_404(instance_id)
    if instance.campaign_id != campaign_id:
        flash('Instance not found in this campaign.', 'danger')
        return redirect(url_for('monsters.list_instances', campaign_id=campaign_id))

    # Sessions available to link (all sessions in this campaign)
    all_sessions = Session.query.filter_by(campaign_id=campaign_id)\
        .order_by(Session.number.desc()).all()

    return render_template('monsters/detail.html', instance=instance,
                           campaign=campaign, all_sessions=all_sessions)


@monsters_bp.route('/<int:instance_id>/edit', methods=['GET', 'POST'])
def edit_instance(campaign_id, instance_id):
    campaign = _check_campaign(campaign_id)
    if not campaign:
        return redirect(url_for('main.index'))

    instance = MonsterInstance.query.get_or_404(instance_id)
    if instance.campaign_id != campaign_id:
        flash('Instance not found in this campaign.', 'danger')
        return redirect(url_for('monsters.list_instances', campaign_id=campaign_id))

    if request.method == 'POST':
        name = request.form.get('instance_name', '').strip()
        if not name:
            flash('Instance name is required.', 'danger')
            return redirect(url_for('monsters.edit_instance',
                                    campaign_id=campaign_id, instance_id=instance_id))

        instance.instance_name = name
        instance.status = request.form.get('status', 'alive')
        instance.notes = request.form.get('notes', '').strip() or None

        # Update session links
        session_ids = [int(i) for i in request.form.getlist('session_ids')]
        instance.sessions = Session.query.filter(Session.id.in_(session_ids)).all()

        db.session.commit()
        flash(f'"{instance.instance_name}" updated.', 'success')
        return redirect(url_for('monsters.instance_detail',
                                campaign_id=campaign_id, instance_id=instance.id))

    all_sessions = Session.query.filter_by(campaign_id=campaign_id)\
        .order_by(Session.number.desc()).all()
    return render_template('monsters/form.html', instance=instance,
                           campaign=campaign, all_sessions=all_sessions,
                           status_choices=INSTANCE_STATUS_CHOICES)


@monsters_bp.route('/<int:instance_id>/delete', methods=['POST'])
def delete_instance(campaign_id, instance_id):
    campaign = _check_campaign(campaign_id)
    if not campaign:
        return redirect(url_for('main.index'))

    instance = MonsterInstance.query.get_or_404(instance_id)
    if instance.campaign_id != campaign_id:
        flash('Instance not found in this campaign.', 'danger')
        return redirect(url_for('monsters.list_instances', campaign_id=campaign_id))

    name = instance.instance_name
    db.session.delete(instance)
    db.session.commit()

    flash(f'"{name}" deleted.', 'warning')
    return redirect(url_for('monsters.list_instances', campaign_id=campaign_id))


@monsters_bp.route('/<int:instance_id>/add-to-session', methods=['POST'])
def add_to_session(campaign_id, instance_id):
    """Quick-link: add this instance to a session from the detail page."""
    campaign = _check_campaign(campaign_id)
    if not campaign:
        return redirect(url_for('main.index'))

    instance = MonsterInstance.query.get_or_404(instance_id)
    if instance.campaign_id != campaign_id:
        flash('Instance not found in this campaign.', 'danger')
        return redirect(url_for('monsters.list_instances', campaign_id=campaign_id))

    sess_id = request.form.get('session_id', type=int)
    if not sess_id:
        flash('Please select a session.', 'warning')
        return redirect(url_for('monsters.instance_detail',
                                campaign_id=campaign_id, instance_id=instance_id))

    sess = Session.query.get(sess_id)
    if sess and sess not in instance.sessions:
        instance.sessions.append(sess)
        db.session.commit()
        flash(f'Added to Session {sess.number}.', 'success')
    elif sess in instance.sessions:
        flash('Already linked to that session.', 'info')

    return redirect(url_for('monsters.instance_detail',
                            campaign_id=campaign_id, instance_id=instance_id))


@monsters_bp.route('/<int:instance_id>/promote', methods=['GET', 'POST'])
def promote_to_npc(campaign_id, instance_id):
    """Convert a Monster Instance into a full NPC."""
    campaign = _check_campaign(campaign_id)
    if not campaign:
        return redirect(url_for('main.index'))

    instance = MonsterInstance.query.get_or_404(instance_id)
    if instance.campaign_id != campaign_id:
        flash('Instance not found in this campaign.', 'danger')
        return redirect(url_for('monsters.list_instances', campaign_id=campaign_id))

    if instance.promoted_to_npc_id:
        flash('This instance has already been promoted to an NPC.', 'info')
        return redirect(url_for('monsters.instance_detail',
                                campaign_id=campaign_id, instance_id=instance_id))

    locations = Location.query.filter_by(campaign_id=campaign_id)\
        .order_by(Location.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('NPC name is required.', 'danger')
            return redirect(url_for('monsters.promote_to_npc',
                                    campaign_id=campaign_id, instance_id=instance_id))

        home_id = request.form.get('home_location_id')
        home_id = int(home_id) if home_id else None

        npc = NPC(
            campaign_id=campaign_id,
            name=name,
            role=request.form.get('role', '').strip() or None,
            status=request.form.get('status', 'alive'),
            faction=request.form.get('faction', '').strip() or None,
            physical_description=request.form.get('physical_description', '').strip() or None,
            personality=request.form.get('personality', '').strip() or None,
            secrets=request.form.get('secrets', '').strip() or None,
            notes=request.form.get('notes', '').strip() or None,
            home_location_id=home_id,
            # Copy the Bestiary Entry image as a starting portrait
            portrait_filename=instance.bestiary_entry.image_path or None,
        )
        db.session.add(npc)
        db.session.flush()  # Gives npc.id before commit

        # Copy session links from instance to the new NPC
        for sess in instance.sessions:
            if npc not in sess.npcs_featured:
                sess.npcs_featured.append(npc)

        # Mark the instance as promoted
        instance.promoted_to_npc_id = npc.id

        db.session.commit()
        flash(f'"{instance.instance_name}" promoted to NPC "{npc.name}"!', 'success')
        return redirect(url_for('npcs.npc_detail', npc_id=npc.id))

    NPC_STATUS_CHOICES = ['alive', 'dead', 'unknown', 'missing']
    return render_template('monsters/promote_form.html', instance=instance,
                           campaign=campaign, locations=locations,
                           status_choices=NPC_STATUS_CHOICES)
