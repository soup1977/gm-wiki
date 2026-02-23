import math
import json
import urllib.request
import urllib.parse
import urllib.error
import markdown as _md

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from app.models import BestiaryEntry

bestiary_import_bp = Blueprint('bestiary_import', __name__, url_prefix='/bestiary/import')

OPEN5E_BASE = 'https://api.open5e.com/v1'

# Standard D&D 5e XP values by CR string
CR_XP = {
    '0': 10, '1/8': 25, '1/4': 50, '1/2': 100,
    '1': 200, '2': 450, '3': 700, '4': 1100,
    '5': 1800, '6': 2300, '7': 2900, '8': 3900,
    '9': 5000, '10': 5900, '11': 7200, '12': 8400,
    '13': 10000, '14': 11500, '15': 13000, '16': 15000,
    '17': 18000, '18': 20000, '19': 22000, '20': 25000,
    '21': 33000, '22': 41000, '23': 50000, '24': 62000,
    '25': 75000, '26': 90000, '27': 105000, '28': 120000,
    '29': 135000, '30': 155000,
}


def _fetch_open5e(path, params=None):
    """Fetch JSON from the Open5e API. Returns parsed dict, or None on error."""
    url = f"{OPEN5E_BASE}{path}"
    if params:
        url += '?' + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GM-Wiki/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None


def _modifier(score):
    """Return a signed modifier string from an ability score (e.g. 14 → '+2')."""
    mod = math.floor((int(score) - 10) / 2)
    return f"+{mod}" if mod >= 0 else str(mod)


def _format_speed(speed_obj):
    """Format the speed dict/string from Open5e into a readable string."""
    if not speed_obj:
        return '—'
    if isinstance(speed_obj, str):
        return speed_obj
    parts = []
    # Walk goes first
    walk = speed_obj.get('walk') or speed_obj.get('walk_')
    if walk:
        parts.append(f"{walk} ft.")
    for mode, val in speed_obj.items():
        if mode in ('walk', 'walk_') or not val:
            continue
        parts.append(f"{mode} {val} ft.")
    return ', '.join(parts) if parts else '—'


def _format_stat_block(m):
    """
    Convert an Open5e monster JSON dict to a Markdown stat block string.
    This produces the same layout you'd see in a rulebook.
    """
    lines = []

    # --- Header line ---
    type_str = m.get('type', '')
    subtype = m.get('subtype', '')
    if subtype:
        type_str += f" ({subtype})"
    size = m.get('size', '')
    alignment = m.get('alignment', '')
    header_parts = [p for p in [size, type_str, alignment] if p]
    lines.append(f"*{', '.join(header_parts)}*")
    lines.append('')

    # --- Core defenses ---
    ac = m.get('armor_class', '')
    ac_desc = m.get('armor_desc', '')
    ac_line = f"**Armor Class** {ac}"
    if ac_desc:
        ac_line += f" ({ac_desc})"
    lines.append(ac_line)

    hp = m.get('hit_points', '')
    hd = m.get('hit_dice', '')
    hp_line = f"**Hit Points** {hp}"
    if hd:
        hp_line += f" ({hd})"
    lines.append(hp_line)

    lines.append(f"**Speed** {_format_speed(m.get('speed'))}")
    lines.append('')

    # --- Ability score table ---
    stats = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
    abbrevs = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']
    lines.append('| ' + ' | '.join(abbrevs) + ' |')
    lines.append('|' + '|'.join(['-----'] * 6) + '|')
    scores = [m.get(s, 10) for s in stats]
    cells = [f"{sc} ({_modifier(sc)})" for sc in scores]
    lines.append('| ' + ' | '.join(cells) + ' |')
    lines.append('')

    # --- Saving throws ---
    save_map = {
        'Str': 'strength_save', 'Dex': 'dexterity_save', 'Con': 'constitution_save',
        'Int': 'intelligence_save', 'Wis': 'wisdom_save', 'Cha': 'charisma_save',
    }
    saves = []
    for label, field in save_map.items():
        val = m.get(field)
        if val is not None:
            saves.append(f"{label} {'+' if int(val) >= 0 else ''}{val}")
    if saves:
        lines.append(f"**Saving Throws** {', '.join(saves)}")

    # --- Skills ---
    skills = m.get('skills') or {}
    if isinstance(skills, dict) and skills:
        skill_parts = []
        for k, v in skills.items():
            # Open5e uses underscores sometimes; normalize to title case with space
            label = k.replace('_', ' ').title()
            skill_parts.append(f"{label} {'+' if int(v) >= 0 else ''}{v}")
        lines.append(f"**Skills** {', '.join(skill_parts)}")

    # --- Damage traits ---
    if m.get('damage_vulnerabilities'):
        lines.append(f"**Damage Vulnerabilities** {m['damage_vulnerabilities']}")
    if m.get('damage_resistances'):
        lines.append(f"**Damage Resistances** {m['damage_resistances']}")
    if m.get('damage_immunities'):
        lines.append(f"**Damage Immunities** {m['damage_immunities']}")
    if m.get('condition_immunities'):
        lines.append(f"**Condition Immunities** {m['condition_immunities']}")

    # --- Senses, languages, challenge ---
    if m.get('senses'):
        lines.append(f"**Senses** {m['senses']}")
    if m.get('languages'):
        lines.append(f"**Languages** {m['languages']}")

    cr = str(m.get('challenge_rating', ''))
    xp = CR_XP.get(cr, '')
    cr_line = f"**Challenge** {cr}"
    if xp:
        cr_line += f" ({xp:,} XP)"
    lines.append(cr_line)

    # --- Special abilities ---
    special = m.get('special_abilities') or []
    if special:
        lines.append('')
        lines.append('---')
        lines.append('')
        for ability in special:
            lines.append(f"**{ability['name']}.** {ability['desc']}")
            lines.append('')

    # --- Actions ---
    actions = m.get('actions') or []
    if actions:
        if not special:
            lines.append('')
            lines.append('---')
            lines.append('')
        lines.append('### Actions')
        lines.append('')
        for action in actions:
            lines.append(f"**{action['name']}.** {action['desc']}")
            lines.append('')

    # --- Bonus Actions ---
    bonus = m.get('bonus_actions') or []
    if bonus:
        lines.append('### Bonus Actions')
        lines.append('')
        for action in bonus:
            lines.append(f"**{action['name']}.** {action['desc']}")
            lines.append('')

    # --- Reactions ---
    reactions = m.get('reactions') or []
    if reactions:
        lines.append('### Reactions')
        lines.append('')
        for reaction in reactions:
            lines.append(f"**{reaction['name']}.** {reaction['desc']}")
            lines.append('')

    # --- Legendary actions ---
    if m.get('legendary_desc'):
        lines.append('### Legendary Actions')
        lines.append('')
        lines.append(m['legendary_desc'])
        lines.append('')
    for la in m.get('legendary_actions') or []:
        lines.append(f"**{la['name']}.** {la['desc']}")
        lines.append('')

    return '\n'.join(lines).strip()


def _build_tags(m):
    """Build a comma-separated tag string from monster type, subtype, and size."""
    parts = []
    if m.get('type'):
        parts.append(m['type'].lower().strip())
    if m.get('subtype'):
        for sub in m['subtype'].lower().replace('(', '').replace(')', '').split(','):
            sub = sub.strip()
            if sub:
                parts.append(sub)
    if m.get('size'):
        parts.append(m['size'].lower().strip())
    return ','.join(parts)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bestiary_import_bp.route('/web')
def import_web():
    return render_template('bestiary/import_web.html')


@bestiary_import_bp.route('/web/search')
def search():
    """AJAX endpoint: proxy a name search to Open5e, return minimal JSON list."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    data = _fetch_open5e('/monsters/', {'search': q, 'limit': 20})
    if data is None:
        return jsonify({'error': 'Could not reach Open5e. Check your internet connection.'}), 502

    results = []
    for r in data.get('results', []):
        results.append({
            'slug': r.get('slug', ''),
            'name': r.get('name', ''),
            'cr': str(r.get('challenge_rating', '')),
            'type': r.get('type', ''),
            'size': r.get('size', ''),
        })
    return jsonify(results)


@bestiary_import_bp.route('/web/preview')
def preview():
    """AJAX endpoint: fetch full creature data from Open5e and return formatted preview."""
    slug = request.args.get('slug', '').strip()
    if not slug:
        return jsonify({'error': 'No slug provided'}), 400

    m = _fetch_open5e(f'/monsters/{slug}/')
    if m is None:
        return jsonify({'error': f'Could not load creature data. Try again.'}), 502

    name = m.get('name', slug)
    stat_block_md = _format_stat_block(m)
    stat_block_html = _md.markdown(stat_block_md, extensions=['tables', 'nl2br'])
    cr = str(m.get('challenge_rating', ''))

    existing = BestiaryEntry.query.filter_by(name=name).first()

    return jsonify({
        'slug': slug,
        'name': name,
        'cr': cr,
        'cr_level': f"CR {cr}" if cr else '',
        'type': m.get('type', ''),
        'size': m.get('size', ''),
        'source': m.get('document__title', 'Open5e SRD'),
        'tags': _build_tags(m),
        'stat_block_html': stat_block_html,
        'exists': existing is not None,
        'existing_id': existing.id if existing else None,
    })


@bestiary_import_bp.route('/web/save', methods=['POST'])
def save():
    """POST handler: fetch creature from Open5e and save as a BestiaryEntry."""
    slug = request.form.get('slug', '').strip()
    if not slug:
        flash('No creature selected.', 'danger')
        return redirect(url_for('bestiary_import.import_web'))

    m = _fetch_open5e(f'/monsters/{slug}/')
    if m is None:
        flash('Could not fetch creature data from Open5e. Please try again.', 'danger')
        return redirect(url_for('bestiary_import.import_web'))

    name = m.get('name', slug)
    force = request.form.get('force', '')

    existing = BestiaryEntry.query.filter_by(name=name).first()
    if existing and not force:
        flash(f'"{name}" already exists in the Bestiary. Use "Import Anyway" on the preview panel to add a duplicate.', 'warning')
        return redirect(url_for('bestiary_import.import_web'))

    cr = str(m.get('challenge_rating', ''))
    entry = BestiaryEntry(
        name=name,
        system='D&D 5e SRD',
        cr_level=f"CR {cr}" if cr else None,
        stat_block=_format_stat_block(m),
        source=m.get('document__title', 'Open5e SRD'),
        tags=_build_tags(m) or None,
        visible_to_players=False,
    )
    db.session.add(entry)
    db.session.commit()

    flash(f'"{name}" imported from Open5e!', 'success')
    return redirect(url_for('bestiary.entry_detail', entry_id=entry.id))
