import json as _json
import os
import random
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, session, jsonify, current_app)
from flask_login import login_required
from app import db
from app.models import RandomTable, TableRow

tables_bp = Blueprint('tables', __name__, url_prefix='/random-tables')


def get_active_campaign_id():
    return session.get('active_campaign_id')


# ── Table listing ─────────────────────────────────────────────────────────────

@tables_bp.route('/')
@login_required
def list_tables():
    campaign_id = get_active_campaign_id()

    if request.args.get('from') != 'session':
        session.pop('in_session_mode', None)
        session.pop('current_session_id', None)
        session.pop('session_title', None)

    tab = request.args.get('tab', 'all')            # all | builtin | custom
    category_filter = request.args.get('category', '')

    # Built-in tables (campaign_id=NULL, is_builtin=True) are always shown
    builtin_q = RandomTable.query.filter_by(is_builtin=True)
    custom_q = RandomTable.query.filter_by(campaign_id=campaign_id, is_builtin=False) if campaign_id else RandomTable.query.filter(False)

    if category_filter:
        builtin_q = builtin_q.filter_by(category=category_filter)
        custom_q = custom_q.filter_by(category=category_filter)

    builtin_tables = builtin_q.order_by(RandomTable.category, RandomTable.name).all()
    custom_tables = custom_q.order_by(RandomTable.category, RandomTable.name).all()

    if tab == 'builtin':
        tables = builtin_tables
    elif tab == 'custom':
        tables = custom_tables
    else:
        tables = builtin_tables + custom_tables

    # Collect all category values for the filter dropdown
    all_categories = sorted({t.category for t in (builtin_tables + custom_tables) if t.category})

    return render_template('tables/list.html',
                           tables=tables,
                           builtin_tables=builtin_tables,
                           custom_tables=custom_tables,
                           tab=tab,
                           all_categories=all_categories,
                           category_filter=category_filter)


# ── Create table ─────────────────────────────────────────────────────────────

@tables_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_table():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Table name is required.', 'danger')
            return render_template('tables/form.html', table=None)

        table = RandomTable(
            campaign_id=campaign_id,
            name=name,
            category=request.form.get('category', '').strip() or None,
            description=request.form.get('description', '').strip() or None,
            is_builtin=False
        )
        db.session.add(table)
        db.session.commit()
        flash(f'Table "{table.name}" created.', 'success')
        return redirect(url_for('tables.table_detail', table_id=table.id))

    return render_template('tables/form.html', table=None)


# ── Table detail ──────────────────────────────────────────────────────────────

@tables_bp.route('/<int:table_id>')
@login_required
def table_detail(table_id):
    campaign_id = get_active_campaign_id()
    table = RandomTable.query.get_or_404(table_id)

    # Restrict access: must own the table or it must be built-in
    if not table.is_builtin and table.campaign_id != campaign_id:
        flash('Table not found in this campaign.', 'danger')
        return redirect(url_for('tables.list_tables'))

    return render_template('tables/detail.html', table=table)


# ── Edit table ────────────────────────────────────────────────────────────────

@tables_bp.route('/<int:table_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_table(table_id):
    campaign_id = get_active_campaign_id()
    table = RandomTable.query.get_or_404(table_id)

    if table.is_builtin:
        flash('Built-in tables cannot be edited.', 'danger')
        return redirect(url_for('tables.table_detail', table_id=table_id))

    if table.campaign_id != campaign_id:
        flash('Table not found in this campaign.', 'danger')
        return redirect(url_for('tables.list_tables'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Table name is required.', 'danger')
            return render_template('tables/form.html', table=table)
        table.name = name
        table.category = request.form.get('category', '').strip() or None
        table.description = request.form.get('description', '').strip() or None
        db.session.commit()
        flash('Table updated.', 'success')
        return redirect(url_for('tables.table_detail', table_id=table.id))

    return render_template('tables/form.html', table=table)


# ── Delete table ──────────────────────────────────────────────────────────────

@tables_bp.route('/<int:table_id>/delete', methods=['POST'])
@login_required
def delete_table(table_id):
    campaign_id = get_active_campaign_id()
    table = RandomTable.query.get_or_404(table_id)

    if table.is_builtin or table.campaign_id != campaign_id:
        flash('Cannot delete this table.', 'danger')
        return redirect(url_for('tables.list_tables'))

    name = table.name
    db.session.delete(table)    # cascade deletes rows
    db.session.commit()
    flash(f'Table "{name}" deleted.', 'warning')
    return redirect(url_for('tables.list_tables'))


# ── Row management ────────────────────────────────────────────────────────────

@tables_bp.route('/<int:table_id>/rows/add', methods=['POST'])
@login_required
def add_row(table_id):
    campaign_id = get_active_campaign_id()
    table = RandomTable.query.get_or_404(table_id)

    if table.is_builtin or table.campaign_id != campaign_id:
        flash('Cannot edit this table.', 'danger')
        return redirect(url_for('tables.table_detail', table_id=table_id))

    content = request.form.get('content', '').strip()
    if not content:
        flash('Row content cannot be empty.', 'danger')
        return redirect(url_for('tables.table_detail', table_id=table_id))

    last = TableRow.query.filter_by(table_id=table_id)\
        .order_by(TableRow.display_order.desc()).first()
    next_order = (last.display_order + 1) if last else 0

    row = TableRow(
        table_id=table_id,
        content=content,
        weight=max(1, int(request.form.get('weight', 1) or 1)),
        display_order=next_order
    )
    db.session.add(row)
    db.session.commit()
    return redirect(url_for('tables.table_detail', table_id=table_id))


@tables_bp.route('/<int:table_id>/rows/<int:row_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_row(table_id, row_id):
    campaign_id = get_active_campaign_id()
    table = RandomTable.query.get_or_404(table_id)
    row = TableRow.query.filter_by(id=row_id, table_id=table_id).first_or_404()

    if table.is_builtin or table.campaign_id != campaign_id:
        flash('Cannot edit this table.', 'danger')
        return redirect(url_for('tables.table_detail', table_id=table_id))

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash('Row content cannot be empty.', 'danger')
            return render_template('tables/row_edit.html', table=table, row=row)
        row.content = content
        row.weight = max(1, int(request.form.get('weight', 1) or 1))
        db.session.commit()
        flash('Row updated.', 'success')
        return redirect(url_for('tables.table_detail', table_id=table_id))

    return render_template('tables/row_edit.html', table=table, row=row)


@tables_bp.route('/<int:table_id>/rows/<int:row_id>/delete', methods=['POST'])
@login_required
def delete_row(table_id, row_id):
    campaign_id = get_active_campaign_id()
    table = RandomTable.query.get_or_404(table_id)
    row = TableRow.query.filter_by(id=row_id, table_id=table_id).first_or_404()

    if table.is_builtin or table.campaign_id != campaign_id:
        flash('Cannot edit this table.', 'danger')
        return redirect(url_for('tables.table_detail', table_id=table_id))

    db.session.delete(row)
    db.session.commit()
    return redirect(url_for('tables.table_detail', table_id=table_id))


@tables_bp.route('/<int:table_id>/rows/<int:row_id>/move', methods=['POST'])
@login_required
def move_row(table_id, row_id):
    campaign_id = get_active_campaign_id()
    table = RandomTable.query.get_or_404(table_id)
    row = TableRow.query.filter_by(id=row_id, table_id=table_id).first_or_404()

    if table.is_builtin or table.campaign_id != campaign_id:
        return redirect(url_for('tables.table_detail', table_id=table_id))

    direction = request.form.get('direction')
    rows = TableRow.query.filter_by(table_id=table_id)\
        .order_by(TableRow.display_order).all()
    idx = next((i for i, r in enumerate(rows) if r.id == row_id), None)

    if idx is None:
        return redirect(url_for('tables.table_detail', table_id=table_id))

    if direction == 'up' and idx > 0:
        swap = rows[idx - 1]
        row.display_order, swap.display_order = swap.display_order, row.display_order
        db.session.commit()
    elif direction == 'down' and idx < len(rows) - 1:
        swap = rows[idx + 1]
        row.display_order, swap.display_order = swap.display_order, row.display_order
        db.session.commit()

    return redirect(url_for('tables.table_detail', table_id=table_id))


# ── Roll endpoint ─────────────────────────────────────────────────────────────

@tables_bp.route('/<int:table_id>/roll')
@login_required
def roll(table_id):
    campaign_id = get_active_campaign_id()
    table = RandomTable.query.get_or_404(table_id)

    if not table.is_builtin and table.campaign_id != campaign_id:
        return jsonify({'error': 'Table not found'}), 404

    rows = table.rows
    if not rows:
        return jsonify({'error': 'Table has no entries'}), 400

    # Build a weighted list: each row appears `weight` times
    weighted = []
    for row in rows:
        weighted.extend([row] * max(1, row.weight))

    selected = random.choice(weighted)
    return jsonify({
        'table_name': table.name,
        'result': selected.content,
        'timestamp': datetime.utcnow().isoformat()
    })


# ── ICRPG seed / clear ──────────────────────────────────────────────────────

@tables_bp.route('/seed-icrpg', methods=['POST'])
@login_required
def seed_icrpg_tables():
    """Load ICRPG roll tables and loot tables as built-in rollable tables."""
    seed_dir = os.path.join(current_app.root_path, 'seed_data')
    imported = 0
    skipped = 0

    def _seed_table(name, category, description, entries):
        nonlocal imported, skipped
        if RandomTable.query.filter_by(name=name, is_builtin=True).first():
            skipped += 1
            return
        table = RandomTable(name=name, category=category,
                            description=description, is_builtin=True)
        db.session.add(table)
        db.session.flush()
        for i, content in enumerate(entries):
            db.session.add(TableRow(table_id=table.id, content=content,
                                    weight=1, display_order=i))
        imported += 1

    # --- d20 Roll Tables (icrpg_tables.json) ---
    tables_path = os.path.join(seed_dir, 'icrpg_tables.json')
    if os.path.exists(tables_path):
        with open(tables_path) as f:
            for t in _json.load(f):
                entries = []
                for e in t['entries']:
                    if e.get('name'):
                        entries.append(f"**{e['name']}** — {e['description']}")
                    else:
                        entries.append(e['description'])
                cat = f"ICRPG - {t.get('category', 'General')}"
                desc = f"{t['die']} table — {t.get('setting', 'ICRPG')}"
                _seed_table(t['table_name'], cat, desc, entries)

    # --- d100 Loot Tables (icrpg_loot.json) ---
    loot_path = os.path.join(seed_dir, 'icrpg_loot.json')
    if os.path.exists(loot_path):
        with open(loot_path) as f:
            for t in _json.load(f):
                entries = []
                for e in t['entries']:
                    entries.append(f"**{e['name']}** ({e['type']}) — {e['description']}")
                _seed_table(t['table_name'], 'ICRPG - Loot', 'd100 loot table', entries)

    # --- Starter Loot (icrpg_starter_loot.json) ---
    starter_path = os.path.join(seed_dir, 'icrpg_starter_loot.json')
    if os.path.exists(starter_path):
        with open(starter_path) as f:
            for t in _json.load(f):
                entries = []
                for e in t['entries']:
                    entries.append(f"**{e['name']}** ({e['type']}) — {e['description']}")
                cat = f"ICRPG - Starter Loot"
                desc = f"{t.get('setting', 'ICRPG')} starter gear"
                _seed_table(t['table_name'], cat, desc, entries)

    db.session.commit()
    msg = f'Loaded {imported} ICRPG rollable tables.'
    if skipped:
        msg += f' Skipped {skipped} duplicates.'
    flash(msg, 'success')
    return redirect(url_for('tables.list_tables'))


@tables_bp.route('/clear-icrpg', methods=['POST'])
@login_required
def clear_icrpg_tables():
    """Delete all ICRPG built-in rollable tables."""
    tables = RandomTable.query.filter(
        RandomTable.is_builtin == True,
        RandomTable.category.like('ICRPG%')
    ).all()
    count = len(tables)
    for t in tables:
        db.session.delete(t)  # cascade deletes rows
    db.session.commit()
    flash(f'Deleted {count} ICRPG rollable tables.', 'success')
    return redirect(url_for('tables.list_tables'))


# ── Import table from URL ────────────────────────────────────────────────────

@tables_bp.route('/import-url', methods=['POST'])
@login_required
def import_from_url():
    """Fetch a URL, use AI to extract a rollable table, return JSON preview."""
    from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError
    import urllib.request
    import re

    data = request.get_json(silent=True)
    if not data or not data.get('url'):
        return jsonify({'error': 'URL is required.'}), 400

    url = data['url'].strip()
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'URL must start with http:// or https://'}), 400

    # Fetch the page content
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 400

    # Strip HTML tags for a rough text extraction
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    # Limit to ~6000 chars to avoid blowing token limits
    if len(text) > 6000:
        text = text[:6000]

    if not is_ai_enabled():
        return jsonify({'error': 'AI is not configured. URL import requires an AI provider.'}), 403

    system_prompt = """You extract rollable random tables from web page text.
Return ONLY valid JSON, no explanation, no markdown fences.
Format: {"name": "Table Name", "entries": ["entry 1", "entry 2", ...]}
- Each entry should be a short, self-contained result suitable for rolling.
- If entries have numbers (like "1. ...", "2. ..."), strip the numbers.
- If the page has multiple tables, pick the largest or most interesting one.
- If no table is found, return: {"error": "No rollable table found on this page."}"""

    messages = [{'role': 'user', 'content': f'Extract a rollable table from this page:\n\n{text}'}]

    try:
        raw = ai_chat(system_prompt, messages, max_tokens=2048, json_mode=True)
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1]
            if raw.endswith('```'):
                raw = raw[:-3].strip()
        result = _json.loads(raw)
        return jsonify(result)
    except _json.JSONDecodeError:
        return jsonify({'error': 'AI returned unexpected output. Try again.'}), 500
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 500


@tables_bp.route('/import-save', methods=['POST'])
@login_required
def import_save():
    """Save a previewed URL-imported table as a custom RandomTable."""
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        return jsonify({'error': 'Select a campaign first.'}), 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    name = (data.get('name') or '').strip()
    entries = data.get('entries', [])

    if not name:
        return jsonify({'error': 'Table name is required.'}), 400
    if not entries:
        return jsonify({'error': 'No entries to import.'}), 400

    table = RandomTable(campaign_id=campaign_id, name=name,
                        category=data.get('category', '').strip() or 'Imported',
                        description=data.get('description', '').strip() or None,
                        is_builtin=False)
    db.session.add(table)
    db.session.flush()
    for i, content in enumerate(entries):
        db.session.add(TableRow(table_id=table.id,
                                content=str(content).strip(),
                                weight=1, display_order=i))
    db.session.commit()
    return jsonify({'success': True, 'table_id': table.id,
                    'redirect': url_for('tables.table_detail', table_id=table.id)})
