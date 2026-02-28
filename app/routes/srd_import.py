"""D&D 5e SRD Import — browse and import spells, items, equipment,
conditions, and rules from the free dnd5eapi.co REST API into
CompendiumEntry records for the active campaign."""

import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required
from app import db
from app.models import CompendiumEntry

srd_import_bp = Blueprint('srd_import', __name__, url_prefix='/srd-import')

API_BASE = 'https://www.dnd5eapi.co'

# Maps a category key to (API list endpoint, CompendiumEntry.category label)
CATEGORIES = {
    'spells':      ('/api/spells',        'D&D 5e - Spell'),
    'magic-items': ('/api/magic-items',   'D&D 5e - Magic Item'),
    'equipment':   ('/api/equipment',     'D&D 5e - Equipment'),
    'conditions':  ('/api/conditions',    'D&D 5e - Condition'),
    'rules':       ('/api/rule-sections', 'D&D 5e - Rule'),
}


def get_active_campaign_id():
    return session.get('active_campaign_id')


# ── Landing page ──────────────────────────────────────────────────────
@srd_import_bp.route('/')
@login_required
def srd_index():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    # Fetch counts from the API for each category
    cat_info = []
    for key, (endpoint, label) in CATEGORIES.items():
        try:
            resp = requests.get(API_BASE + endpoint, timeout=10)
            data = resp.json()
            count = data.get('count', len(data.get('results', [])))
        except Exception:
            count = '?'

        # How many already imported in this campaign?
        imported = CompendiumEntry.query.filter_by(
            campaign_id=campaign_id, category=label
        ).count()

        cat_info.append({
            'key': key,
            'label': label,
            'count': count,
            'imported': imported,
        })

    return render_template('srd_import/index.html', categories=cat_info)


# ── Browse a category ─────────────────────────────────────────────────
@srd_import_bp.route('/browse/<category>')
@login_required
def browse(category):
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    if category not in CATEGORIES:
        flash('Unknown category.', 'danger')
        return redirect(url_for('srd_import.srd_index'))

    endpoint, label = CATEGORIES[category]

    try:
        resp = requests.get(API_BASE + endpoint, timeout=10)
        data = resp.json()
        items = data.get('results', [])
    except Exception:
        flash('Could not reach dnd5eapi.co. Try again later.', 'danger')
        return redirect(url_for('srd_import.srd_index'))

    # Check which are already imported
    existing = set(
        e.title for e in CompendiumEntry.query.filter_by(
            campaign_id=campaign_id, category=label
        ).all()
    )

    return render_template('srd_import/browse.html',
                           category=category, label=label,
                           items=items, existing=existing)


# ── Import selected items ─────────────────────────────────────────────
@srd_import_bp.route('/import', methods=['POST'])
@login_required
def do_import():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    category = request.form.get('category', '')
    if category not in CATEGORIES:
        flash('Unknown category.', 'danger')
        return redirect(url_for('srd_import.srd_index'))

    _endpoint, label = CATEGORIES[category]
    selected = request.form.getlist('selected')

    if not selected:
        flash('No items selected.', 'warning')
        return redirect(url_for('srd_import.browse', category=category))

    imported = 0
    skipped = 0

    for item_url in selected:
        # item_url is the API path like "/api/spells/fireball"
        try:
            resp = requests.get(API_BASE + item_url, timeout=10)
            detail = resp.json()
        except Exception:
            continue

        title = detail.get('name', 'Unknown')

        # Skip if already exists
        exists = CompendiumEntry.query.filter_by(
            campaign_id=campaign_id, category=label, title=title
        ).first()
        if exists:
            skipped += 1
            continue

        body = _format_detail(category, detail)

        entry = CompendiumEntry(
            campaign_id=campaign_id,
            title=title,
            category=label,
            content=body,
            is_gm_only=False,
        )
        db.session.add(entry)
        imported += 1

    db.session.commit()

    msg = f'Imported {imported} {label} entries.'
    if skipped:
        msg += f' Skipped {skipped} duplicates.'
    flash(msg, 'success')
    return redirect(url_for('srd_import.browse', category=category))


# ── Format API detail into markdown ───────────────────────────────────
def _format_detail(category, d):
    """Convert a dnd5eapi.co detail response into a readable markdown body."""
    if category == 'spells':
        return _format_spell(d)
    elif category == 'magic-items':
        return _format_magic_item(d)
    elif category == 'equipment':
        return _format_equipment(d)
    elif category == 'conditions':
        return _format_condition(d)
    elif category == 'rules':
        return _format_rule(d)
    return d.get('desc', str(d))


def _format_spell(d):
    lines = []
    lines.append(f"**Level:** {d.get('level', '?')}")
    if d.get('school'):
        lines.append(f"**School:** {d['school'].get('name', '')}")
    lines.append(f"**Casting Time:** {d.get('casting_time', '?')}")
    lines.append(f"**Range:** {d.get('range', '?')}")

    # Components
    comps = ', '.join(d.get('components', []))
    if d.get('material'):
        comps += f" ({d['material']})"
    lines.append(f"**Components:** {comps}")

    lines.append(f"**Duration:** {d.get('duration', '?')}")
    if d.get('concentration'):
        lines.append("**Concentration:** Yes")

    lines.append('')
    for desc in d.get('desc', []):
        lines.append(desc)
        lines.append('')

    if d.get('higher_level'):
        lines.append('**At Higher Levels:**')
        for hl in d['higher_level']:
            lines.append(hl)

    if d.get('classes'):
        cls_names = [c.get('name', '') for c in d['classes']]
        lines.append(f"\n**Classes:** {', '.join(cls_names)}")

    return '\n'.join(lines)


def _format_magic_item(d):
    lines = []
    if d.get('equipment_category'):
        lines.append(f"**Type:** {d['equipment_category'].get('name', '')}")
    if d.get('rarity'):
        lines.append(f"**Rarity:** {d['rarity'].get('name', '')}")

    lines.append('')
    for desc in d.get('desc', []):
        lines.append(desc)
        lines.append('')
    return '\n'.join(lines)


def _format_equipment(d):
    lines = []
    if d.get('equipment_category'):
        lines.append(f"**Category:** {d['equipment_category'].get('name', '')}")
    if d.get('cost'):
        lines.append(f"**Cost:** {d['cost'].get('quantity', '')} {d['cost'].get('unit', '')}")
    if d.get('weight'):
        lines.append(f"**Weight:** {d['weight']} lb.")
    if d.get('damage'):
        dmg = d['damage']
        lines.append(f"**Damage:** {dmg.get('damage_dice', '')} {dmg.get('damage_type', {}).get('name', '')}")
    if d.get('armor_class'):
        ac = d['armor_class']
        lines.append(f"**AC:** {ac.get('base', '')} {'+ Dex' if ac.get('dex_bonus') else ''}")

    lines.append('')
    for desc in d.get('desc', []):
        lines.append(desc)
        lines.append('')
    return '\n'.join(lines)


def _format_condition(d):
    lines = []
    for desc in d.get('desc', []):
        lines.append(desc)
        lines.append('')
    return '\n'.join(lines)


def _format_rule(d):
    return d.get('desc', '')
