import random
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, session, jsonify)
from app import db
from app.models import RandomTable, TableRow

tables_bp = Blueprint('tables', __name__, url_prefix='/random-tables')


def get_active_campaign_id():
    return session.get('active_campaign_id')


# ── Table listing ─────────────────────────────────────────────────────────────

@tables_bp.route('/')
def list_tables():
    campaign_id = get_active_campaign_id()
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
