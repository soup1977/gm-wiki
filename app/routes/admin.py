from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import User, ActivityLog, Campaign, AppSetting

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator that checks current_user.is_admin, returns 403 if not."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users')
@login_required
@admin_required
def list_users():
    users = User.query.order_by(User.username).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        is_admin = 'is_admin' in request.form
        role = request.form.get('role', 'player')
        if role not in ('gm', 'asst_gm', 'player'):
            role = 'player'

        if not username:
            flash('Username is required.', 'danger')
            return render_template('admin/user_form.html', user=None)
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('admin/user_form.html', user=None)
        if User.query.filter_by(username=username).first():
            flash(f'Username "{username}" is already taken.', 'danger')
            return render_template('admin/user_form.html', user=None)

        user = User(username=username, is_admin=is_admin, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        ActivityLog.log_event('created', 'user', username, entity_id=user.id)

        flash(f'User "{username}" created.', 'success')
        return redirect(url_for('admin.list_users'))

    return render_template('admin/user_form.html', user=None)


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '')
    if len(new_password) < 8:
        flash('Password must be at least 8 characters.', 'danger')
        return redirect(url_for('admin.list_users'))

    user.set_password(new_password)
    db.session.commit()
    flash(f'Password reset for "{user.username}".', 'success')
    return redirect(url_for('admin.list_users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.list_users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    ActivityLog.log_event('deleted', 'user', username, entity_id=user_id)
    flash(f'User "{username}" deleted.', 'warning')
    return redirect(url_for('admin.list_users'))


# ═══════════════════════════════════════════════════════════════════════════
# ACTIVITY LOG
# ═══════════════════════════════════════════════════════════════════════════

ENTITY_URL_MAP = {
    'npc':            ('npcs.npc_detail',              'npc_id'),
    'location':       ('locations.location_detail',    'location_id'),
    'quest':          ('quests.quest_detail',          'quest_id'),
    'item':           ('items.item_detail',            'item_id'),
    'session':        ('sessions.session_detail',      'session_id'),
    'encounter':      ('encounters.encounter_detail',  'encounter_id'),
    'faction':        ('factions.faction_detail',       'faction_id'),
    'compendium':     ('compendium.entry_detail',      'entry_id'),
    'adventure_site': ('adventure_sites.site_detail',  'site_id'),
    'pc':             ('pcs.pc_detail',                'pc_id'),
    'bestiary':       ('bestiary.entry_detail',        'entry_id'),
    'campaign':       ('campaigns.campaign_detail',    'campaign_id'),
    'random_table':   ('tables.table_detail',          'table_id'),
}


def _entity_url(entry):
    """Build a detail-page URL for a log entry, or None if not linkable."""
    if not entry.entity_id or entry.action == 'deleted':
        return None
    mapping = ENTITY_URL_MAP.get(entry.entity_type)
    if not mapping:
        return None
    endpoint, param = mapping
    try:
        return url_for(endpoint, **{param: entry.entity_id})
    except Exception:
        return None


@admin_bp.route('/activity-log')
@login_required
@admin_required
def activity_log():
    campaign_id = request.args.get('campaign_id', type=int)
    entity_type = request.args.get('entity_type', '').strip() or None
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action', '').strip() or None

    page = request.args.get('page', 1, type=int)
    per_page = 50

    query = ActivityLog.query.order_by(ActivityLog.timestamp.desc())
    if campaign_id:
        query = query.filter_by(campaign_id=campaign_id)
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter_by(action=action)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    campaigns = Campaign.query.order_by(Campaign.name).all()
    users = User.query.order_by(User.username).all()

    entity_types = sorted(set(
        r[0] for r in db.session.query(ActivityLog.entity_type).distinct().all()
    )) or []

    actions = ['created', 'edited', 'deleted', 'status_changed', 'error']

    # Pre-compute detail-page URLs for each entry
    for entry in pagination.items:
        entry._url = _entity_url(entry)

    return render_template('admin/activity_log.html',
                           entries=pagination.items,
                           pagination=pagination,
                           campaigns=campaigns,
                           users=users,
                           entity_types=entity_types,
                           actions=actions,
                           filter_campaign_id=campaign_id,
                           filter_entity_type=entity_type,
                           filter_user_id=user_id,
                           filter_action=action)


@admin_bp.route('/activity-log/purge', methods=['POST'])
@login_required
@admin_required
def purge_activity_log():
    from datetime import datetime, timedelta
    days = int(AppSetting.get('activity_log_retention_days', '90'))
    cutoff = datetime.utcnow() - timedelta(days=days)
    count = ActivityLog.query.filter(ActivityLog.timestamp < cutoff).delete()
    db.session.commit()
    flash(f'Purged {count} log entries older than {days} days.', 'info')
    return redirect(url_for('admin.activity_log'))
