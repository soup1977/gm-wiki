from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required
from app import db, save_upload
from app.models import PlayerCharacter, PlayerCharacterStat, CampaignStatTemplate

pcs_bp = Blueprint('pcs', __name__, url_prefix='/pcs')

PC_STATUS_CHOICES = ['active', 'inactive', 'retired', 'dead', 'npc']


def get_active_campaign_id():
    return session.get('active_campaign_id')


def _save_stats(pc, campaign_id):
    """Read stat_<field_id> values from the request form and save them to
    PlayerCharacterStat rows. Creates a row for any template field that doesn't
    have one yet (handles both create and edit paths)."""
    template_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()

    # Build a lookup: template_field_id → existing stat row (if any)
    existing = {s.template_field_id: s for s in pc.stats}

    for field in template_fields:
        value = request.form.get(f'stat_{field.id}', '').strip()
        if field.id in existing:
            existing[field.id].stat_value = value
        else:
            db.session.add(PlayerCharacterStat(
                character_id=pc.id,
                template_field_id=field.id,
                stat_value=value
            ))


@pcs_bp.route('/')
@login_required
def list_pcs():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    session.pop('in_session_mode', None)
    session.pop('current_session_id', None)
    session.pop('session_title', None)

    status_filter = request.args.get('status', 'all')
    query = PlayerCharacter.query.filter_by(campaign_id=campaign_id)
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    pcs = query.order_by(PlayerCharacter.character_name).all()

    # Pass the first 3 template fields so the list can show a quick stat preview
    preview_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).limit(3).all()

    return render_template('pcs/list.html', pcs=pcs,
                           status_filter=status_filter,
                           status_choices=PC_STATUS_CHOICES,
                           preview_fields=preview_fields)


@pcs_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_pc():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    template_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()

    if request.method == 'POST':
        character_name = request.form.get('character_name', '').strip()
        player_name = request.form.get('player_name', '').strip()
        if not character_name or not player_name:
            flash('Character name and player name are both required.', 'danger')
            return render_template('pcs/form.html', pc=None,
                                   template_fields=template_fields,
                                   status_choices=PC_STATUS_CHOICES)

        pc = PlayerCharacter(
            campaign_id=campaign_id,
            character_name=character_name,
            player_name=player_name,
            level_or_rank=request.form.get('level_or_rank', '').strip(),
            class_or_role=request.form.get('class_or_role', '').strip(),
            status=request.form.get('status', 'active'),
            backstory=request.form.get('backstory', '').strip() or None,
            gm_hooks=request.form.get('gm_hooks', '').strip() or None,
            notes=request.form.get('notes', '').strip()
        )
        db.session.add(pc)
        db.session.flush()  # Assigns pc.id so we can create stat rows

        _save_stats(pc, campaign_id)

        portrait_file = request.files.get('portrait')
        filename = save_upload(portrait_file)
        if filename:
            pc.portrait_filename = filename

        db.session.commit()
        flash(f'"{pc.character_name}" created!', 'success')
        return redirect(url_for('pcs.pc_detail', pc_id=pc.id))

    return render_template('pcs/form.html', pc=None,
                           template_fields=template_fields,
                           status_choices=PC_STATUS_CHOICES)


@pcs_bp.route('/<int:pc_id>')
@login_required
def pc_detail(pc_id):
    campaign_id = get_active_campaign_id()
    pc = PlayerCharacter.query.get_or_404(pc_id)
    if pc.campaign_id != campaign_id:
        flash('Character not found in this campaign.', 'danger')
        return redirect(url_for('pcs.list_pcs'))

    if request.args.get('from') != 'session':
        session.pop('in_session_mode', None)
        session.pop('current_session_id', None)
        session.pop('session_title', None)

    # Build an ordered list of (field_name, value) for display
    template_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()
    stat_lookup = {s.template_field_id: s.stat_value for s in pc.stats}
    stats_display = [
        (field.stat_name, stat_lookup.get(field.id, ''))
        for field in template_fields
    ]

    return render_template('pcs/detail.html', pc=pc, stats_display=stats_display)


@pcs_bp.route('/<int:pc_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_pc(pc_id):
    campaign_id = get_active_campaign_id()
    pc = PlayerCharacter.query.get_or_404(pc_id)
    if pc.campaign_id != campaign_id:
        flash('Character not found in this campaign.', 'danger')
        return redirect(url_for('pcs.list_pcs'))

    template_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()

    if request.method == 'POST':
        character_name = request.form.get('character_name', '').strip()
        player_name = request.form.get('player_name', '').strip()
        if not character_name or not player_name:
            flash('Character name and player name are both required.', 'danger')
            return render_template('pcs/form.html', pc=pc,
                                   template_fields=template_fields,
                                   status_choices=PC_STATUS_CHOICES)

        pc.character_name = character_name
        pc.player_name = player_name
        pc.level_or_rank = request.form.get('level_or_rank', '').strip()
        pc.class_or_role = request.form.get('class_or_role', '').strip()
        pc.status = request.form.get('status', 'active')
        pc.backstory = request.form.get('backstory', '').strip() or None
        pc.gm_hooks = request.form.get('gm_hooks', '').strip() or None
        pc.notes = request.form.get('notes', '').strip()

        _save_stats(pc, campaign_id)

        portrait_file = request.files.get('portrait')
        filename = save_upload(portrait_file)
        if filename:
            pc.portrait_filename = filename

        db.session.commit()
        flash(f'"{pc.character_name}" updated!', 'success')
        return redirect(url_for('pcs.pc_detail', pc_id=pc.id))

    # Build existing stat values for the form
    stat_values = {s.template_field_id: s.stat_value for s in pc.stats}
    return render_template('pcs/form.html', pc=pc,
                           template_fields=template_fields,
                           stat_values=stat_values,
                           status_choices=PC_STATUS_CHOICES)


@pcs_bp.route('/<int:pc_id>/delete', methods=['POST'])
@login_required
def delete_pc(pc_id):
    campaign_id = get_active_campaign_id()
    pc = PlayerCharacter.query.get_or_404(pc_id)
    if pc.campaign_id != campaign_id:
        flash('Character not found in this campaign.', 'danger')
        return redirect(url_for('pcs.list_pcs'))

    name = pc.character_name
    # cascade='all, delete-orphan' on pc.stats handles PlayerCharacterStat rows
    db.session.delete(pc)
    db.session.commit()

    flash(f'"{name}" deleted.', 'warning')
    return redirect(url_for('pcs.list_pcs'))
