from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from flask_login import login_required, current_user
from app import db, save_upload
from app.models import (PlayerCharacter, PlayerCharacterStat, CampaignStatTemplate,
                         Location, Campaign, ICRPGCharacterSheet, ICRPGCharLoot,
                         ICRPGCharAbility, ICRPGWorld, ICRPGLifeForm, ICRPGType,
                         ICRPGAbility, ICRPGStartingLoot, ICRPGLootDef, ICRPGSpell)

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


def _can_edit(pc):
    """Check if the current user can edit this PC."""
    if current_user.is_admin:
        return True
    if not pc.user_id:
        return True  # Unclaimed — any logged-in user can edit
    return pc.user_id == current_user.id


def _is_owner(pc):
    """True if the current user is the claiming player (not admin)."""
    return (pc.user_id and pc.user_id == current_user.id
            and not current_user.is_admin)


def _build_sheet_catalog(campaign_id):
    """Build a JSON-serializable catalog dict for the Add Loot/Ability modals."""
    loot_defs = ICRPGLootDef.query.filter(
        db.or_(ICRPGLootDef.is_builtin == True,
               ICRPGLootDef.campaign_id == campaign_id)
    ).order_by(ICRPGLootDef.name).all()

    spells = ICRPGSpell.query.filter(
        db.or_(ICRPGSpell.is_builtin == True,
               ICRPGSpell.campaign_id == campaign_id)
    ).order_by(ICRPGSpell.name).all()

    abilities = ICRPGAbility.query.filter(
        db.or_(ICRPGAbility.is_builtin == True,
               ICRPGAbility.campaign_id == campaign_id)
    ).order_by(ICRPGAbility.ability_kind, ICRPGAbility.name).all()

    return {
        'loot_defs': [
            {'id': ld.id, 'name': ld.name, 'loot_type': ld.loot_type or '',
             'description': ld.description or '', 'slot_cost': ld.slot_cost,
             'effects': ld.effects, 'world_id': ld.world_id}
            for ld in loot_defs
        ],
        'spells': [
            {'id': sp.id, 'name': sp.name, 'spell_type': sp.spell_type or '',
             'casting_stat': sp.casting_stat or '',
             'description': sp.description or ''}
            for sp in spells
        ],
        'abilities': [
            {'id': ab.id, 'name': ab.name, 'description': ab.description or '',
             'ability_kind': ab.ability_kind,
             'type_id': ab.type_id,
             'type_name': ab.type_ref.name if ab.type_ref else ''}
            for ab in abilities
        ],
    }


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

    campaign = Campaign.query.get(campaign_id)
    is_icrpg = 'icrpg' in (campaign.system or '').lower() if campaign else False

    return render_template('pcs/list.html', pcs=pcs,
                           status_filter=status_filter,
                           status_choices=PC_STATUS_CHOICES,
                           preview_fields=preview_fields,
                           is_icrpg=is_icrpg)


@pcs_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_pc():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    template_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()
    locations = Location.query.filter_by(campaign_id=campaign_id)\
        .order_by(Location.name).all()

    if request.method == 'POST':
        character_name = request.form.get('character_name', '').strip()
        player_name = request.form.get('player_name', '').strip()
        if not character_name or not player_name:
            flash('Character name and player name are both required.', 'danger')
            return render_template('pcs/form.html', pc=None,
                                   template_fields=template_fields,
                                   locations=locations, is_owner=False,
                                   status_choices=PC_STATUS_CHOICES)

        home_id = request.form.get('home_location_id')
        home_id = int(home_id) if home_id else None

        pc = PlayerCharacter(
            campaign_id=campaign_id,
            character_name=character_name,
            player_name=player_name,
            race_or_ancestry=request.form.get('race_or_ancestry', '').strip() or None,
            level_or_rank=request.form.get('level_or_rank', '').strip(),
            class_or_role=request.form.get('class_or_role', '').strip(),
            status=request.form.get('status', 'active'),
            description=request.form.get('description', '').strip() or None,
            backstory=request.form.get('backstory', '').strip() or None,
            gm_hooks=request.form.get('gm_hooks', '').strip() or None,
            notes=request.form.get('notes', '').strip(),
            home_location_id=home_id,
        )
        db.session.add(pc)
        db.session.flush()  # Assigns pc.id so we can create stat rows

        _save_stats(pc, campaign_id)

        portrait_file = request.files.get('portrait')
        filename = save_upload(portrait_file)
        if not filename:
            filename = request.form.get('sd_generated_filename', '').strip() or None
        if filename:
            pc.portrait_filename = filename

        db.session.commit()
        flash(f'"{pc.character_name}" created!', 'success')
        return redirect(url_for('pcs.pc_detail', pc_id=pc.id))

    return render_template('pcs/form.html', pc=None,
                           template_fields=template_fields,
                           locations=locations, is_owner=False,
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

    # Check if this is an ICRPG campaign — show the ICRPG sheet instead
    campaign = Campaign.query.get(campaign_id)
    is_icrpg = 'icrpg' in (campaign.system or '').lower()

    if is_icrpg:
        sheet = pc.icrpg_sheet  # 1:1 backref, may be None
        if sheet:
            # Build catalog for Add Loot / Add Ability modals (anyone who can edit)
            sheet_catalog = None
            if _can_edit(pc):
                sheet_catalog = _build_sheet_catalog(campaign_id)
                sheet_catalog['char_type_id'] = sheet.type_id
                sheet_catalog['char_world_id'] = sheet.world_id
            can_edit_stats = current_user.is_admin or (
                sheet.allow_player_edit and _is_owner(pc)
            )
            return render_template('pcs/icrpg_sheet.html',
                                   pc=pc, sheet=sheet,
                                   can_edit=_can_edit(pc),
                                   can_edit_stats=can_edit_stats,
                                   is_owner=_is_owner(pc),
                                   sheet_catalog=sheet_catalog)
        else:
            return render_template('pcs/detail.html', pc=pc,
                                   stats_display=stats_display,
                                   can_edit=_can_edit(pc),
                                   show_icrpg_banner=True)

    return render_template('pcs/detail.html', pc=pc, stats_display=stats_display,
                           can_edit=_can_edit(pc))


@pcs_bp.route('/<int:pc_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_pc(pc_id):
    campaign_id = get_active_campaign_id()
    pc = PlayerCharacter.query.get_or_404(pc_id)
    if pc.campaign_id != campaign_id:
        flash('Character not found in this campaign.', 'danger')
        return redirect(url_for('pcs.list_pcs'))

    if not _can_edit(pc):
        flash('You do not have permission to edit this character.', 'danger')
        return redirect(url_for('pcs.pc_detail', pc_id=pc.id))

    owner = _is_owner(pc)

    template_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()
    locations = Location.query.filter_by(campaign_id=campaign_id)\
        .order_by(Location.name).all()

    if request.method == 'POST':
        character_name = request.form.get('character_name', '').strip()
        player_name = request.form.get('player_name', '').strip()
        if not character_name or not player_name:
            flash('Character name and player name are both required.', 'danger')
            return render_template('pcs/form.html', pc=pc,
                                   template_fields=template_fields,
                                   locations=locations, is_owner=owner,
                                   status_choices=PC_STATUS_CHOICES)

        # Player-editable fields (always saved)
        pc.character_name = character_name
        pc.player_name = player_name
        pc.race_or_ancestry = request.form.get('race_or_ancestry', '').strip() or None
        pc.class_or_role = request.form.get('class_or_role', '').strip()
        pc.level_or_rank = request.form.get('level_or_rank', '').strip()
        pc.description = request.form.get('description', '').strip() or None
        pc.backstory = request.form.get('backstory', '').strip() or None

        # GM-only fields (skip if player is editing their own claimed PC)
        if not owner:
            pc.status = request.form.get('status', 'active')
            pc.gm_hooks = request.form.get('gm_hooks', '').strip() or None
            pc.notes = request.form.get('notes', '').strip()
            home_id = request.form.get('home_location_id')
            pc.home_location_id = int(home_id) if home_id else None

        _save_stats(pc, campaign_id)

        portrait_file = request.files.get('portrait')
        filename = save_upload(portrait_file)
        if not filename:
            filename = request.form.get('sd_generated_filename', '').strip() or None
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
                           locations=locations, is_owner=owner,
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


@pcs_bp.route('/<int:pc_id>/claim', methods=['POST'])
@login_required
def claim_pc(pc_id):
    campaign_id = get_active_campaign_id()
    pc = PlayerCharacter.query.get_or_404(pc_id)
    if pc.campaign_id != campaign_id:
        flash('Character not found in this campaign.', 'danger')
        return redirect(url_for('pcs.list_pcs'))
    if pc.user_id:
        flash('This character is already claimed.', 'warning')
        return redirect(url_for('pcs.pc_detail', pc_id=pc.id))
    pc.user_id = current_user.id
    db.session.commit()
    flash(f'You claimed "{pc.character_name}"!', 'success')
    return redirect(url_for('pcs.pc_detail', pc_id=pc.id))


@pcs_bp.route('/<int:pc_id>/unclaim', methods=['POST'])
@login_required
def unclaim_pc(pc_id):
    campaign_id = get_active_campaign_id()
    pc = PlayerCharacter.query.get_or_404(pc_id)
    if pc.campaign_id != campaign_id:
        flash('Character not found in this campaign.', 'danger')
        return redirect(url_for('pcs.list_pcs'))
    if pc.user_id != current_user.id and not current_user.is_admin:
        flash('You can only unclaim your own character.', 'danger')
        return redirect(url_for('pcs.pc_detail', pc_id=pc.id))
    pc.user_id = None
    db.session.commit()
    flash(f'"{pc.character_name}" is now unclaimed.', 'info')
    return redirect(url_for('pcs.pc_detail', pc_id=pc.id))


# ═══════════════════════════════════════════════════════════════════════════
# ICRPG QUICK-EDIT ENDPOINTS (AJAX, return JSON)
# ═══════════════════════════════════════════════════════════════════════════

def _get_sheet_or_error(pc_id):
    """Load PC + ICRPG sheet with campaign and permission checks.
    Returns (sheet, error_response). If error_response is not None, return it."""
    pc = PlayerCharacter.query.get(pc_id)
    if not pc or pc.campaign_id != get_active_campaign_id():
        return None, (jsonify({'error': 'Not found.'}), 404)
    if not _can_edit(pc):
        return None, (jsonify({'error': 'Permission denied.'}), 403)
    sheet = pc.icrpg_sheet
    if not sheet:
        return None, (jsonify({'error': 'No ICRPG sheet.'}), 404)
    return sheet, None


@pcs_bp.route('/<int:pc_id>/icrpg/hp', methods=['POST'])
@login_required
def icrpg_adjust_hp(pc_id):
    """Adjust HP by a delta (+1 or -1). Clamps to 0..hp_max."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    delta = int(data.get('delta', 0))
    sheet.hp_current = max(0, min(sheet.hp_current + delta, sheet.hp_max))
    db.session.commit()
    return jsonify({'hp_current': sheet.hp_current, 'hp_max': sheet.hp_max})


@pcs_bp.route('/<int:pc_id>/icrpg/hero-coin', methods=['POST'])
@login_required
def icrpg_toggle_hero_coin(pc_id):
    """Toggle hero coin on/off."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    sheet.hero_coin = not sheet.hero_coin
    db.session.commit()
    return jsonify({'hero_coin': sheet.hero_coin})


@pcs_bp.route('/<int:pc_id>/icrpg/dying', methods=['POST'])
@login_required
def icrpg_adjust_dying(pc_id):
    """Adjust dying timer by a delta. Clamps to 0..3."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    delta = int(data.get('delta', 0))
    sheet.dying_timer = max(0, min(sheet.dying_timer + delta, 3))
    db.session.commit()
    return jsonify({'dying_timer': sheet.dying_timer})


@pcs_bp.route('/<int:pc_id>/icrpg/nat20', methods=['POST'])
@login_required
def icrpg_increment_nat20(pc_id):
    """Increment nat 20 count. Auto-awards mastery at 20 (resets counter)."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    sheet.nat20_count += 1
    if sheet.nat20_count >= 20 and sheet.mastery_count < 3:
        sheet.mastery_count += 1
        sheet.nat20_count = 0
    db.session.commit()
    return jsonify({
        'nat20_count': sheet.nat20_count,
        'mastery_count': sheet.mastery_count,
    })


@pcs_bp.route('/<int:pc_id>/icrpg/equip', methods=['POST'])
@login_required
def icrpg_equip_loot(pc_id):
    """Move loot between equipped and carried slots."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    loot_id = data.get('loot_id')
    new_slot = data.get('slot')
    if new_slot not in ('equipped', 'carried'):
        return jsonify({'error': 'Invalid slot.'}), 400
    char_loot = ICRPGCharLoot.query.filter_by(id=loot_id, sheet_id=sheet.id).first()
    if not char_loot:
        return jsonify({'error': 'Loot not found.'}), 404
    # Check slot capacity when equipping
    if new_slot == 'equipped':
        cost = char_loot.loot_def.slot_cost if char_loot.loot_def else 1
        if sheet.equipped_slots_used + cost > 10:
            return jsonify({'error': 'Not enough equipped slots.'}), 400
    char_loot.slot = new_slot
    db.session.commit()
    return jsonify({'ok': True})


@pcs_bp.route('/<int:pc_id>/icrpg/update-stat', methods=['POST'])
@login_required
def icrpg_update_stat(pc_id):
    """Adjust a base stat by +1/-1. GM or player with toggle."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    if not current_user.is_admin:
        if not (sheet.allow_player_edit and sheet.pc.user_id == current_user.id):
            return jsonify({'error': 'GM only.'}), 403
    data = request.get_json(silent=True) or {}
    key = data.get('key', '').lower()
    delta = int(data.get('delta', 0))
    if key not in ('str', 'dex', 'con', 'int', 'wis', 'cha'):
        return jsonify({'error': 'Invalid stat.'}), 400
    attr = f'stat_{key}'
    current = getattr(sheet, attr) or 0
    new_val = max(0, min(current + delta, 10))
    setattr(sheet, attr, new_val)
    db.session.commit()
    return jsonify({
        'key': key.upper(), 'base': new_val,
        'total': sheet.total_stat(key.upper()),
        'defense': sheet.defense,
    })


@pcs_bp.route('/<int:pc_id>/icrpg/update-effort', methods=['POST'])
@login_required
def icrpg_update_effort(pc_id):
    """Adjust a base effort by +1/-1. GM or player with toggle."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    if not current_user.is_admin:
        if not (sheet.allow_player_edit and sheet.pc.user_id == current_user.id):
            return jsonify({'error': 'GM only.'}), 403
    data = request.get_json(silent=True) or {}
    key = data.get('key', '').lower()
    delta = int(data.get('delta', 0))
    if key not in ('basic', 'weapons', 'guns', 'magic', 'ultimate'):
        return jsonify({'error': 'Invalid effort.'}), 400
    attr = f'effort_{key}'
    current = getattr(sheet, attr) or 0
    new_val = max(0, min(current + delta, 10))
    setattr(sheet, attr, new_val)
    db.session.commit()
    return jsonify({
        'key': key, 'base': new_val,
        'total': sheet.total_effort(key),
    })


@pcs_bp.route('/<int:pc_id>/icrpg/toggle-player-edit', methods=['POST'])
@login_required
def icrpg_toggle_player_edit(pc_id):
    """Toggle whether the owning player can edit base stats/efforts. GM only."""
    if not current_user.is_admin:
        return jsonify({'error': 'GM only.'}), 403
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    sheet.allow_player_edit = not sheet.allow_player_edit
    db.session.commit()
    return jsonify({'allow_player_edit': sheet.allow_player_edit})


@pcs_bp.route('/<int:pc_id>/icrpg/add-loot', methods=['POST'])
@login_required
def icrpg_add_loot(pc_id):
    """Add a loot item to the character sheet."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    loot_def_id = data.get('loot_def_id')
    spell_id = data.get('spell_id')
    slot = data.get('slot', 'carried')
    if slot not in ('equipped', 'carried'):
        slot = 'carried'

    if loot_def_id:
        if not ICRPGLootDef.query.get(loot_def_id):
            return jsonify({'error': 'Loot not found.'}), 404
    elif spell_id:
        if not ICRPGSpell.query.get(spell_id):
            return jsonify({'error': 'Spell not found.'}), 404
    else:
        # Custom item — must have at least a name
        custom_name = (data.get('custom_name') or '').strip()
        if not custom_name:
            return jsonify({'error': 'Must specify loot_def_id, spell_id, or custom_name.'}), 400

    new_item = ICRPGCharLoot(
        sheet_id=sheet.id,
        loot_def_id=loot_def_id,
        spell_id=spell_id,
        custom_name=data.get('custom_name'),
        custom_desc=data.get('custom_desc'),
        slot=slot,
        display_order=len(sheet.loot_items),
    )
    db.session.add(new_item)
    db.session.commit()
    return jsonify({'ok': True, 'id': new_item.id})


@pcs_bp.route('/<int:pc_id>/icrpg/remove-loot', methods=['POST'])
@login_required
def icrpg_remove_loot(pc_id):
    """Remove a loot item from the character sheet."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    loot_id = data.get('loot_id')
    char_loot = ICRPGCharLoot.query.filter_by(id=loot_id, sheet_id=sheet.id).first()
    if not char_loot:
        return jsonify({'error': 'Loot not found.'}), 404
    db.session.delete(char_loot)
    db.session.commit()
    return jsonify({'ok': True})


@pcs_bp.route('/<int:pc_id>/icrpg/add-ability', methods=['POST'])
@login_required
def icrpg_add_ability(pc_id):
    """Add an ability to the character sheet."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    ability_id = data.get('ability_id')
    ability_kind = data.get('ability_kind', 'starting')
    warning = None
    if ability_id:
        ab = ICRPGAbility.query.get(ability_id)
        if not ab:
            return jsonify({'error': 'Ability not found.'}), 404
        ability_kind = ab.ability_kind
        # Soft warning for cross-type ability
        if ab.type_id and sheet.type_id and ab.type_id != sheet.type_id:
            type_name = ab.type_ref.name if ab.type_ref else 'another type'
            warning = f'This ability belongs to {type_name}, not your type.'
    new_ab = ICRPGCharAbility(
        sheet_id=sheet.id,
        ability_id=ability_id,
        ability_kind=ability_kind,
        custom_name=data.get('custom_name'),
        custom_desc=data.get('custom_desc'),
        display_order=len(sheet.char_abilities),
    )
    db.session.add(new_ab)
    db.session.commit()
    resp = {'ok': True, 'id': new_ab.id}
    if warning:
        resp['warning'] = warning
    return jsonify(resp)


@pcs_bp.route('/<int:pc_id>/icrpg/remove-ability', methods=['POST'])
@login_required
def icrpg_remove_ability(pc_id):
    """Remove an ability from the character sheet."""
    sheet, err = _get_sheet_or_error(pc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    char_ab_id = data.get('ability_id')
    char_ab = ICRPGCharAbility.query.filter_by(id=char_ab_id, sheet_id=sheet.id).first()
    if not char_ab:
        return jsonify({'error': 'Ability not found.'}), 404
    db.session.delete(char_ab)
    db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════
# ICRPG CHARACTER CREATION WIZARD
# ═══════════════════════════════════════════════════════════════════════════

def _serialize_catalog(worlds, life_forms, types):
    """Build catalog dict for JSON embedding in the wizard template."""
    return {
        'worlds': [
            {'id': w.id, 'name': w.name, 'description': w.description or ''}
            for w in worlds
        ],
        'life_forms': [
            {'id': lf.id, 'world_id': lf.world_id, 'name': lf.name,
             'description': lf.description or '', 'bonuses': lf.bonuses or {}}
            for lf in life_forms
        ],
        'types': [
            {
                'id': t.id, 'world_id': t.world_id, 'name': t.name,
                'description': t.description or '',
                'starting_abilities': [
                    {'id': a.id, 'name': a.name, 'description': a.description or ''}
                    for a in t.abilities if a.ability_kind == 'starting'
                ],
                'starting_loot': [
                    {
                        'id': sl.id,
                        'name': sl.display_name,
                        'description': (sl.loot_def.description if sl.loot_def else
                                        sl.spell.description if sl.spell else ''),
                        'loot_type': (sl.loot_def.loot_type if sl.loot_def else 'Spell'),
                        'loot_def_id': sl.loot_def_id,
                        'spell_id': sl.spell_id,
                    }
                    for sl in t.starting_loot
                ],
            }
            for t in types
        ],
    }


@pcs_bp.route('/icrpg/wizard')
@login_required
def icrpg_wizard():
    """Render the 8-step ICRPG character creation wizard."""
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    campaign = Campaign.query.get(campaign_id)
    if not campaign or 'icrpg' not in (campaign.system or '').lower():
        flash('The ICRPG wizard is only available for ICRPG campaigns.', 'danger')
        return redirect(url_for('pcs.list_pcs'))

    # Query catalog: builtin + campaign homebrew
    worlds = ICRPGWorld.query.filter(
        db.or_(ICRPGWorld.is_builtin == True,
               ICRPGWorld.campaign_id == campaign_id)
    ).order_by(ICRPGWorld.name).all()

    world_ids = [w.id for w in worlds]

    life_forms = ICRPGLifeForm.query.filter(
        ICRPGLifeForm.world_id.in_(world_ids)
    ).order_by(ICRPGLifeForm.name).all()

    types = ICRPGType.query.filter(
        ICRPGType.world_id.in_(world_ids)
    ).order_by(ICRPGType.name).all()

    catalog_json = _serialize_catalog(worlds, life_forms, types)

    return render_template('pcs/icrpg_wizard.html', catalog_json=catalog_json)


@pcs_bp.route('/icrpg/create', methods=['POST'])
@login_required
def icrpg_create_character():
    """Create a PlayerCharacter + ICRPGCharacterSheet from the wizard."""
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400

    campaign = Campaign.query.get(campaign_id)
    if not campaign or 'icrpg' not in (campaign.system or '').lower():
        return jsonify({'error': 'Not an ICRPG campaign.'}), 400

    data = request.get_json(silent=True) or {}

    # ── Validate text fields ──────────────────────────────────
    character_name = (data.get('character_name') or '').strip()
    player_name = (data.get('player_name') or '').strip()
    if not character_name or not player_name:
        return jsonify({'error': 'Character name and player name are required.'}), 400

    story = (data.get('story') or '').strip()[:500]

    # ── Validate world ────────────────────────────────────────
    world_id = data.get('world_id')
    world = ICRPGWorld.query.get(world_id) if world_id else None
    if not world or not (world.is_builtin or world.campaign_id == campaign_id):
        return jsonify({'error': 'Invalid world.'}), 400

    # ── Validate life form ────────────────────────────────────
    life_form_id = data.get('life_form_id')
    life_form = ICRPGLifeForm.query.get(life_form_id) if life_form_id else None
    if not life_form or life_form.world_id != world.id:
        return jsonify({'error': 'Invalid life form.'}), 400

    # ── Validate type ─────────────────────────────────────────
    type_id = data.get('type_id')
    type_obj = ICRPGType.query.get(type_id) if type_id else None
    if not type_obj or type_obj.world_id != world.id:
        return jsonify({'error': 'Invalid type.'}), 400

    # ── Validate stats (6 points total, each 0-6) ────────────
    stats = data.get('stats', {})
    stat_keys = ['str', 'dex', 'con', 'int', 'wis', 'cha']
    try:
        stat_values = {k: int(stats.get(k, 0)) for k in stat_keys}
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid stat values.'}), 400
    if any(v < 0 or v > 6 for v in stat_values.values()):
        return jsonify({'error': 'Each stat must be 0-6.'}), 400
    if sum(stat_values.values()) != 6:
        return jsonify({'error': 'Stats must total exactly 6.'}), 400

    # ── Validate effort (4 points total, each 0-4) ───────────
    effort = data.get('effort', {})
    effort_keys = ['basic', 'weapons', 'guns', 'magic', 'ultimate']
    try:
        effort_values = {k: int(effort.get(k, 0)) for k in effort_keys}
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid effort values.'}), 400
    if any(v < 0 or v > 4 for v in effort_values.values()):
        return jsonify({'error': 'Each effort must be 0-4.'}), 400
    if sum(effort_values.values()) != 4:
        return jsonify({'error': 'Effort must total exactly 4.'}), 400

    # ── Validate abilities ────────────────────────────────────
    ability_ids = data.get('ability_ids', [])
    valid_starting = ICRPGAbility.query.filter_by(
        type_id=type_obj.id, ability_kind='starting').all()
    valid_ab_ids = {a.id for a in valid_starting}
    for ab_id in ability_ids:
        if ab_id not in valid_ab_ids:
            return jsonify({'error': 'Invalid ability selection.'}), 400

    # ── Validate loot picks ───────────────────────────────────
    loot_picks = data.get('loot_picks', [])
    valid_sl = ICRPGStartingLoot.query.filter_by(type_id=type_obj.id).all()
    valid_loot_keys = {(sl.loot_def_id, sl.spell_id) for sl in valid_sl}
    for pick in loot_picks:
        key = (pick.get('loot_def_id'), pick.get('spell_id'))
        if key not in valid_loot_keys:
            return jsonify({'error': 'Invalid loot selection.'}), 400

    # ── Create records ────────────────────────────────────────
    pc = PlayerCharacter(
        campaign_id=campaign_id,
        character_name=character_name,
        player_name=player_name,
        race_or_ancestry=life_form.name,
        class_or_role=type_obj.name,
        status='active',
    )
    db.session.add(pc)
    db.session.flush()

    sheet = ICRPGCharacterSheet(
        pc_id=pc.id,
        world_id=world.id,
        life_form_id=life_form.id,
        type_id=type_obj.id,
        story=story,
        stat_str=stat_values['str'],
        stat_dex=stat_values['dex'],
        stat_con=stat_values['con'],
        stat_int=stat_values['int'],
        stat_wis=stat_values['wis'],
        stat_cha=stat_values['cha'],
        effort_basic=effort_values['basic'],
        effort_weapons=effort_values['weapons'],
        effort_guns=effort_values['guns'],
        effort_magic=effort_values['magic'],
        effort_ultimate=effort_values['ultimate'],
        hearts_max=1,
        hp_current=10,
        hero_coin=True,
    )
    # Handle life form HEARTS bonus
    bonuses = life_form.bonuses or {}
    if isinstance(bonuses.get('HEARTS'), (int, float)):
        sheet.hearts_max += int(bonuses['HEARTS'])
        sheet.hp_current = sheet.hearts_max * 10

    db.session.add(sheet)
    db.session.flush()

    for i, ab_id in enumerate(ability_ids):
        db.session.add(ICRPGCharAbility(
            sheet_id=sheet.id, ability_id=ab_id,
            ability_kind='starting', display_order=i
        ))

    for i, pick in enumerate(loot_picks):
        db.session.add(ICRPGCharLoot(
            sheet_id=sheet.id,
            loot_def_id=pick.get('loot_def_id'),
            spell_id=pick.get('spell_id'),
            slot='equipped', display_order=i
        ))

    db.session.commit()

    return jsonify({
        'ok': True,
        'pc_id': pc.id,
        'redirect': url_for('pcs.pc_detail', pc_id=pc.id),
    })


@pcs_bp.route('/<int:pc_id>/icrpg/create-sheet', methods=['POST'])
@login_required
def icrpg_create_sheet(pc_id):
    """Create a blank ICRPG sheet for a PC. GM/admin only."""
    campaign_id = get_active_campaign_id()
    pc = PlayerCharacter.query.get_or_404(pc_id)
    if pc.campaign_id != campaign_id:
        flash('Character not found in this campaign.', 'danger')
        return redirect(url_for('pcs.list_pcs'))
    if not current_user.is_admin:
        flash('Only the GM can create ICRPG sheets.', 'danger')
        return redirect(url_for('pcs.pc_detail', pc_id=pc.id))
    if pc.icrpg_sheet:
        flash('This character already has an ICRPG sheet.', 'info')
        return redirect(url_for('pcs.pc_detail', pc_id=pc.id))
    sheet = ICRPGCharacterSheet(pc_id=pc.id)
    db.session.add(sheet)
    db.session.commit()
    flash(f'ICRPG sheet created for "{pc.character_name}".', 'success')
    return redirect(url_for('pcs.pc_detail', pc_id=pc.id))
