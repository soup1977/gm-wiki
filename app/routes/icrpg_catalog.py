"""
ICRPG Homebrew Catalog CRUD.
Single tabbed page for managing custom worlds, life forms, types,
abilities, loot, spells, and milestone paths — scoped to the active campaign.
"""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from flask_login import login_required, current_user
from app import db
from app.models import (Campaign, ICRPGWorld, ICRPGLifeForm, ICRPGType,
                         ICRPGAbility, ICRPGLootDef, ICRPGSpell,
                         ICRPGMilestonePath)

icrpg_catalog_bp = Blueprint('icrpg_catalog', __name__,
                              url_prefix='/icrpg-catalog')


def _get_campaign_or_error():
    """Return (campaign, campaign_id) or redirect with flash."""
    cid = session.get('active_campaign_id')
    if not cid:
        flash('Select a campaign first.', 'warning')
        return None, None
    campaign = Campaign.query.get(cid)
    if not campaign:
        flash('Campaign not found.', 'danger')
        return None, None
    if 'icrpg' not in (campaign.system or '').lower():
        flash('This campaign is not ICRPG.', 'warning')
        return None, None
    return campaign, cid


def _gm_only():
    """Return a JSON 403 if user is not admin."""
    if not current_user.is_admin:
        return jsonify({'error': 'GM only.'}), 403
    return None


def _own_homebrew(model, item_id, campaign_id):
    """Fetch a homebrew item by id, verifying it belongs to this campaign
    and is not builtin. Returns (item, error_response)."""
    item = model.query.get(item_id)
    if not item:
        return None, (jsonify({'error': 'Not found.'}), 404)
    if item.is_builtin or item.campaign_id != campaign_id:
        return None, (jsonify({'error': 'Cannot modify this item.'}), 403)
    return item, None


# ═══════════════════════════════════════════════════════════════════════════
# INDEX — Tabbed catalog page
# ═══════════════════════════════════════════════════════════════════════════

@icrpg_catalog_bp.route('/')
@login_required
def index():
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return redirect(url_for('main.index'))
    if not current_user.is_admin:
        flash('GM only.', 'danger')
        return redirect(url_for('main.index'))

    # Homebrew items for this campaign
    hw = ICRPGWorld.query.filter_by(campaign_id=cid, is_builtin=False).order_by(ICRPGWorld.name).all()
    hlf = ICRPGLifeForm.query.filter_by(campaign_id=cid, is_builtin=False).order_by(ICRPGLifeForm.name).all()
    ht = ICRPGType.query.filter_by(campaign_id=cid, is_builtin=False).order_by(ICRPGType.name).all()
    hab = ICRPGAbility.query.filter_by(campaign_id=cid, is_builtin=False).order_by(ICRPGAbility.name).all()
    hld = ICRPGLootDef.query.filter_by(campaign_id=cid, is_builtin=False).order_by(ICRPGLootDef.name).all()
    hsp = ICRPGSpell.query.filter_by(campaign_id=cid, is_builtin=False).order_by(ICRPGSpell.name).all()
    hmp = ICRPGMilestonePath.query.filter_by(campaign_id=cid, is_builtin=False).order_by(ICRPGMilestonePath.name).all()

    # Builtin items (read-only display)
    bw = ICRPGWorld.query.filter_by(is_builtin=True).order_by(ICRPGWorld.name).all()
    blf = ICRPGLifeForm.query.filter_by(is_builtin=True).order_by(ICRPGLifeForm.name).all()
    bt = ICRPGType.query.filter_by(is_builtin=True).order_by(ICRPGType.name).all()
    bab = ICRPGAbility.query.filter_by(is_builtin=True).order_by(ICRPGAbility.name).all()
    bld = ICRPGLootDef.query.filter_by(is_builtin=True).order_by(ICRPGLootDef.name).all()
    bsp = ICRPGSpell.query.filter_by(is_builtin=True).order_by(ICRPGSpell.name).all()
    bmp = ICRPGMilestonePath.query.filter_by(is_builtin=True).order_by(ICRPGMilestonePath.name).all()

    # All worlds + types visible to this campaign (for dropdown parents)
    all_worlds = ICRPGWorld.query.filter(
        db.or_(ICRPGWorld.is_builtin == True, ICRPGWorld.campaign_id == cid)
    ).order_by(ICRPGWorld.name).all()
    all_types = ICRPGType.query.filter(
        db.or_(ICRPGType.is_builtin == True, ICRPGType.campaign_id == cid)
    ).order_by(ICRPGType.name).all()

    return render_template('icrpg_catalog/index.html',
                           campaign=campaign,
                           hw=hw, hlf=hlf, ht=ht, hab=hab, hld=hld, hsp=hsp, hmp=hmp,
                           bw=bw, blf=blf, bt=bt, bab=bab, bld=bld, bsp=bsp, bmp=bmp,
                           all_worlds=all_worlds, all_types=all_types,
                           tab=request.args.get('tab', 'worlds'))


# ═══════════════════════════════════════════════════════════════════════════
# WORLDS CRUD
# ═══════════════════════════════════════════════════════════════════════════

@icrpg_catalog_bp.route('/worlds/create', methods=['POST'])
@login_required
def create_world():
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    blc = int(data.get('basic_loot_count', 4))
    if blc < 0:
        blc = 0
    w = ICRPGWorld(name=name, description=(data.get('description') or '').strip(),
                   is_builtin=False, campaign_id=cid, basic_loot_count=blc)
    db.session.add(w)
    db.session.commit()
    return jsonify({'ok': True, 'id': w.id})


@icrpg_catalog_bp.route('/worlds/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_world(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGWorld, item_id, cid)
    if item_err: return item_err
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    item.name = name
    item.description = (data.get('description') or '').strip()
    blc = int(data.get('basic_loot_count', item.basic_loot_count or 4))
    if blc < 0:
        blc = 0
    item.basic_loot_count = blc
    db.session.commit()
    return jsonify({'ok': True})


@icrpg_catalog_bp.route('/worlds/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_world(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGWorld, item_id, cid)
    if item_err: return item_err
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════
# LIFE FORMS CRUD
# ═══════════════════════════════════════════════════════════════════════════

@icrpg_catalog_bp.route('/life-forms/create', methods=['POST'])
@login_required
def create_life_form():
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    bonuses = data.get('bonuses') or {}
    if isinstance(bonuses, str):
        import json
        try:
            bonuses = json.loads(bonuses)
        except (json.JSONDecodeError, ValueError):
            return jsonify({'error': 'Invalid bonuses JSON.'}), 400
    lf = ICRPGLifeForm(
        world_id=data.get('world_id'), name=name,
        description=(data.get('description') or '').strip(),
        bonuses=bonuses, is_builtin=False, campaign_id=cid)
    db.session.add(lf)
    db.session.commit()
    return jsonify({'ok': True, 'id': lf.id})


@icrpg_catalog_bp.route('/life-forms/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_life_form(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGLifeForm, item_id, cid)
    if item_err: return item_err
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    bonuses = data.get('bonuses') or {}
    if isinstance(bonuses, str):
        import json
        try:
            bonuses = json.loads(bonuses)
        except (json.JSONDecodeError, ValueError):
            return jsonify({'error': 'Invalid bonuses JSON.'}), 400
    item.world_id = data.get('world_id')
    item.name = name
    item.description = (data.get('description') or '').strip()
    item.bonuses = bonuses
    db.session.commit()
    return jsonify({'ok': True})


@icrpg_catalog_bp.route('/life-forms/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_life_form(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGLifeForm, item_id, cid)
    if item_err: return item_err
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════
# TYPES CRUD
# ═══════════════════════════════════════════════════════════════════════════

@icrpg_catalog_bp.route('/types/create', methods=['POST'])
@login_required
def create_type():
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    t = ICRPGType(world_id=data.get('world_id'), name=name,
                  description=(data.get('description') or '').strip(),
                  is_builtin=False, campaign_id=cid)
    db.session.add(t)
    db.session.commit()
    return jsonify({'ok': True, 'id': t.id})


@icrpg_catalog_bp.route('/types/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_type(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGType, item_id, cid)
    if item_err: return item_err
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    item.world_id = data.get('world_id')
    item.name = name
    item.description = (data.get('description') or '').strip()
    db.session.commit()
    return jsonify({'ok': True})


@icrpg_catalog_bp.route('/types/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_type(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGType, item_id, cid)
    if item_err: return item_err
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════
# ABILITIES CRUD
# ═══════════════════════════════════════════════════════════════════════════

@icrpg_catalog_bp.route('/abilities/create', methods=['POST'])
@login_required
def create_ability():
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    kind = data.get('ability_kind', 'starting')
    if kind not in ('starting', 'milestone', 'mastery'):
        kind = 'starting'
    ab = ICRPGAbility(
        type_id=data.get('type_id'), name=name,
        description=(data.get('description') or '').strip(),
        ability_kind=kind, is_builtin=False, campaign_id=cid)
    db.session.add(ab)
    db.session.commit()
    return jsonify({'ok': True, 'id': ab.id})


@icrpg_catalog_bp.route('/abilities/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_ability(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGAbility, item_id, cid)
    if item_err: return item_err
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    kind = data.get('ability_kind', item.ability_kind)
    if kind not in ('starting', 'milestone', 'mastery'):
        kind = item.ability_kind
    item.type_id = data.get('type_id')
    item.name = name
    item.description = (data.get('description') or '').strip()
    item.ability_kind = kind
    db.session.commit()
    return jsonify({'ok': True})


@icrpg_catalog_bp.route('/abilities/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_ability(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGAbility, item_id, cid)
    if item_err: return item_err
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════
# LOOT DEFS CRUD
# ═══════════════════════════════════════════════════════════════════════════

@icrpg_catalog_bp.route('/loot/create', methods=['POST'])
@login_required
def create_loot():
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    effects = data.get('effects') or {}
    if isinstance(effects, str):
        import json
        try:
            effects = json.loads(effects)
        except (json.JSONDecodeError, ValueError):
            return jsonify({'error': 'Invalid effects JSON.'}), 400
    ld = ICRPGLootDef(
        world_id=data.get('world_id'), name=name,
        loot_type=(data.get('loot_type') or '').strip(),
        description=(data.get('description') or '').strip(),
        effects=effects,
        slot_cost=int(data.get('slot_cost', 1)),
        coin_cost=int(data.get('coin_cost', 0)) if data.get('coin_cost') else 0,
        is_starter=bool(data.get('is_starter', False)),
        is_builtin=False, campaign_id=cid)
    db.session.add(ld)
    db.session.commit()
    return jsonify({'ok': True, 'id': ld.id})


@icrpg_catalog_bp.route('/loot/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_loot(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGLootDef, item_id, cid)
    if item_err: return item_err
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    effects = data.get('effects') or {}
    if isinstance(effects, str):
        import json
        try:
            effects = json.loads(effects)
        except (json.JSONDecodeError, ValueError):
            return jsonify({'error': 'Invalid effects JSON.'}), 400
    item.world_id = data.get('world_id')
    item.name = name
    item.loot_type = (data.get('loot_type') or '').strip()
    item.description = (data.get('description') or '').strip()
    item.effects = effects
    item.slot_cost = int(data.get('slot_cost', item.slot_cost))
    item.coin_cost = int(data.get('coin_cost', 0)) if data.get('coin_cost') else 0
    item.is_starter = bool(data.get('is_starter', item.is_starter))
    db.session.commit()
    return jsonify({'ok': True})


@icrpg_catalog_bp.route('/loot/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_loot(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGLootDef, item_id, cid)
    if item_err: return item_err
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════
# SPELLS CRUD
# ═══════════════════════════════════════════════════════════════════════════

@icrpg_catalog_bp.route('/spells/create', methods=['POST'])
@login_required
def create_spell():
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    sp = ICRPGSpell(
        name=name,
        spell_type=(data.get('spell_type') or '').strip(),
        casting_stat=(data.get('casting_stat') or '').strip().upper(),
        level=int(data.get('level', 1)),
        target=(data.get('target') or '').strip(),
        duration=(data.get('duration') or '').strip(),
        description=(data.get('description') or '').strip(),
        is_builtin=False, campaign_id=cid)
    db.session.add(sp)
    db.session.commit()
    return jsonify({'ok': True, 'id': sp.id})


@icrpg_catalog_bp.route('/spells/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_spell(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGSpell, item_id, cid)
    if item_err: return item_err
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    item.name = name
    item.spell_type = (data.get('spell_type') or '').strip()
    item.casting_stat = (data.get('casting_stat') or '').strip().upper()
    item.level = int(data.get('level', item.level))
    item.target = (data.get('target') or '').strip()
    item.duration = (data.get('duration') or '').strip()
    item.description = (data.get('description') or '').strip()
    db.session.commit()
    return jsonify({'ok': True})


@icrpg_catalog_bp.route('/spells/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_spell(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGSpell, item_id, cid)
    if item_err: return item_err
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════
# MILESTONE PATHS CRUD
# ═══════════════════════════════════════════════════════════════════════════

@icrpg_catalog_bp.route('/paths/create', methods=['POST'])
@login_required
def create_path():
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    tiers = data.get('tiers') or []
    if isinstance(tiers, str):
        import json
        try:
            tiers = json.loads(tiers)
        except (json.JSONDecodeError, ValueError):
            return jsonify({'error': 'Invalid tiers JSON.'}), 400
    mp = ICRPGMilestonePath(
        name=name, description=(data.get('description') or '').strip(),
        tiers=tiers, is_builtin=False, campaign_id=cid)
    db.session.add(mp)
    db.session.commit()
    return jsonify({'ok': True, 'id': mp.id})


@icrpg_catalog_bp.route('/paths/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_path(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGMilestonePath, item_id, cid)
    if item_err: return item_err
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    tiers = data.get('tiers') or item.tiers
    if isinstance(tiers, str):
        import json
        try:
            tiers = json.loads(tiers)
        except (json.JSONDecodeError, ValueError):
            return jsonify({'error': 'Invalid tiers JSON.'}), 400
    item.name = name
    item.description = (data.get('description') or '').strip()
    item.tiers = tiers
    db.session.commit()
    return jsonify({'ok': True})


@icrpg_catalog_bp.route('/paths/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_path(item_id):
    err = _gm_only()
    if err: return err
    campaign, cid = _get_campaign_or_error()
    if not campaign:
        return jsonify({'error': 'No ICRPG campaign.'}), 400
    item, item_err = _own_homebrew(ICRPGMilestonePath, item_id, cid)
    if item_err: return item_err
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})
