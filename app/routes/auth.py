from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from app import db
from app.models import User, Campaign

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If no users exist yet, redirect to first-run setup
    if User.query.count() == 0:
        return redirect(url_for('auth.setup'))

    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))

        flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    # Only available when zero users exist
    if User.query.count() > 0:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username:
            flash('Username is required.', 'danger')
            return render_template('auth/setup.html')
        if len(password) < 4:
            flash('Password must be at least 4 characters.', 'danger')
            return render_template('auth/setup.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/setup.html')

        # Create the admin user
        admin = User(username=username, is_admin=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.flush()

        # Assign all existing orphaned campaigns to the admin
        orphaned = Campaign.query.filter_by(user_id=None).all()
        for campaign in orphaned:
            campaign.user_id = admin.id

        db.session.commit()

        login_user(admin)
        flash(f'Welcome, {username}! Your admin account has been created.', 'success')
        if orphaned:
            flash(f'{len(orphaned)} existing campaign(s) have been assigned to your account.', 'info')
        return redirect(url_for('main.index'))

    return render_template('auth/setup.html')
