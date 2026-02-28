import re
from collections import defaultdict
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required
from app import db, save_upload
from app.models import BestiaryEntry, MonsterInstance, Campaign
from app.shortcode import process_shortcodes, clear_mentions

bestiary_bp = Blueprint('bestiary', __name__, url_prefix='/bestiary')


def get_active_campaign_id():
    return session.get('active_campaign_id')


def _all_tags():
    """Collect all unique tags from all Bestiary Entries, sorted."""
    entries = BestiaryEntry.query.all()
    tag_set = set()
    for entry in entries:
        tag_set.update(entry.get_tags_list())
    return sorted(tag_set)


def _auto_instance_name(entry, campaign_id):
    """Generate the next sequential instance name for a Bestiary Entry.
    E.g. if 'Goblin 1' and 'Goblin 2' exist, returns 'Goblin 3'."""
    existing = MonsterInstance.query.filter_by(
        bestiary_entry_id=entry.id,
        campaign_id=campaign_id
    ).all()

    if not existing:
        return f"{entry.name} 1"

    # Find the highest trailing number among existing instance names
    highest = 0
    for inst in existing:
        match = re.search(r'(\d+)$', inst.instance_name)
        if match:
            num = int(match.group(1))
            if num > highest:
                highest = num

    return f"{entry.name} {highest + 1}"


@bestiary_bp.route('/')
@login_required
def list_bestiary():
    active_tag = request.args.get('tag', '').strip().lower() or None
    search = request.args.get('q', '').strip() or None

    query = BestiaryEntry.query

    if search:
        query = query.filter(BestiaryEntry.name.ilike(f'%{search}%'))

    entries = query.order_by(BestiaryEntry.name).all()

    # Apply tag filter in Python (tags stored as comma-separated string)
    if active_tag:
        entries = [e for e in entries if active_tag in e.get_tags_list()]

    all_tags = _all_tags()

    # Group by system for list view
    groups = defaultdict(list)
    for entry in entries:
        key = entry.system or 'Unspecified'
        groups[key].append(entry)
    grouped_entries = dict(sorted(groups.items()))

    return render_template('bestiary/index.html', entries=entries,
                           grouped_entries=grouped_entries,
                           all_tags=all_tags, active_tag=active_tag, search=search)


@bestiary_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_entry():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name is required.', 'danger')
            return redirect(url_for('bestiary.create_entry'))

        stat_block = request.form.get('stat_block', '').strip()
        if not stat_block:
            flash('Stat block is required.', 'danger')
            return redirect(url_for('bestiary.create_entry'))

        # Normalize tags to lowercase comma-separated
        raw_tags = request.form.get('tags', '').strip()
        normalized_tags = ','.join(
            t.strip().lower() for t in raw_tags.split(',') if t.strip()
        )

        entry = BestiaryEntry(
            name=name,
            system=request.form.get('system', '').strip() or None,
            cr_level=request.form.get('cr_level', '').strip() or None,
            stat_block=stat_block,
            source=request.form.get('source', '').strip() or None,
            visible_to_players='visible_to_players' in request.form,
            tags=normalized_tags or None,
        )
        db.session.add(entry)

        image_file = request.files.get('image')
        filename = save_upload(image_file)
        if not filename:
            filename = request.form.get('sd_generated_filename', '').strip() or None
        if filename:
            entry.image_path = filename

        # Process shortcodes using the active campaign for entity scoping
        campaign_id = get_active_campaign_id()
        if campaign_id and entry.stat_block:
            db.session.flush()
            processed, mentions = process_shortcodes(entry.stat_block, campaign_id, 'bestiary', entry.id)
            entry.stat_block = processed
            for m in mentions:
                db.session.add(m)

        db.session.commit()
        flash(f'"{entry.name}" added to the Bestiary!', 'success')
        return redirect(url_for('bestiary.entry_detail', entry_id=entry.id))

    return render_template('bestiary/form.html', entry=None)


@bestiary_bp.route('/<int:entry_id>')
@login_required
def entry_detail(entry_id):
    entry = BestiaryEntry.query.get_or_404(entry_id)

    # Group instances by campaign for display
    campaigns = {}
    for inst in entry.instances:
        cname = inst.campaign.name
        campaigns.setdefault(cname, []).append(inst)

    return render_template('bestiary/detail.html', entry=entry,
                           instances_by_campaign=campaigns)


@bestiary_bp.route('/<int:entry_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    entry = BestiaryEntry.query.get_or_404(entry_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name is required.', 'danger')
            return redirect(url_for('bestiary.edit_entry', entry_id=entry.id))

        stat_block = request.form.get('stat_block', '').strip()
        if not stat_block:
            flash('Stat block is required.', 'danger')
            return redirect(url_for('bestiary.edit_entry', entry_id=entry.id))

        raw_tags = request.form.get('tags', '').strip()
        normalized_tags = ','.join(
            t.strip().lower() for t in raw_tags.split(',') if t.strip()
        )

        entry.name = name
        entry.system = request.form.get('system', '').strip() or None
        entry.cr_level = request.form.get('cr_level', '').strip() or None
        entry.stat_block = stat_block
        entry.source = request.form.get('source', '').strip() or None
        entry.visible_to_players = 'visible_to_players' in request.form
        entry.tags = normalized_tags or None

        image_file = request.files.get('image')
        filename = save_upload(image_file)
        if not filename:
            filename = request.form.get('sd_generated_filename', '').strip() or None
        if filename:
            entry.image_path = filename

        campaign_id = get_active_campaign_id()
        if campaign_id and entry.stat_block:
            clear_mentions('bestiary', entry.id)
            processed, mentions = process_shortcodes(entry.stat_block, campaign_id, 'bestiary', entry.id)
            entry.stat_block = processed
            for m in mentions:
                db.session.add(m)

        db.session.commit()
        flash(f'"{entry.name}" updated.', 'success')
        return redirect(url_for('bestiary.entry_detail', entry_id=entry.id))

    return render_template('bestiary/form.html', entry=entry)


@bestiary_bp.route('/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = BestiaryEntry.query.get_or_404(entry_id)
    instance_count = len(entry.instances)
    name = entry.name

    # cascade='all, delete-orphan' on the relationship handles instances automatically
    db.session.delete(entry)
    db.session.commit()

    msg = f'"{name}" deleted from Bestiary.'
    if instance_count:
        msg += f' ({instance_count} monster instance(s) also removed.)'
    flash(msg, 'warning')
    return redirect(url_for('bestiary.list_bestiary'))


@bestiary_bp.route('/<int:entry_id>/spawn', methods=['POST'])
@login_required
def spawn_instance(entry_id):
    """Create a MonsterInstance from this Bestiary Entry in the active campaign."""
    entry = BestiaryEntry.query.get_or_404(entry_id)
    campaign_id = get_active_campaign_id()

    if not campaign_id:
        flash('Please select a campaign before spawning an instance.', 'warning')
        return redirect(url_for('bestiary.entry_detail', entry_id=entry_id))

    # Use provided name or auto-generate
    instance_name = request.form.get('instance_name', '').strip()
    if not instance_name:
        instance_name = _auto_instance_name(entry, campaign_id)

    instance = MonsterInstance(
        bestiary_entry_id=entry.id,
        campaign_id=campaign_id,
        instance_name=instance_name,
        status='alive',
    )
    db.session.add(instance)
    db.session.commit()

    flash(f'Spawned "{instance.instance_name}"!', 'success')
    return redirect(url_for('monsters.instance_detail',
                            campaign_id=campaign_id, instance_id=instance.id))
