from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import User

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

        if not username:
            flash('Username is required.', 'danger')
            return render_template('admin/user_form.html', user=None)
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('admin/user_form.html', user=None)
        if User.query.filter_by(username=username).first():
            flash(f'Username "{username}" is already taken.', 'danger')
            return render_template('admin/user_form.html', user=None)

        user = User(username=username, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

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
    flash(f'User "{username}" deleted.', 'warning')
    return redirect(url_for('admin.list_users'))
