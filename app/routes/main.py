from flask import Blueprint, render_template, session, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Campaign

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    campaigns = Campaign.query.filter_by(user_id=current_user.id).order_by(Campaign.name).all()
    active_campaign_id = session.get('active_campaign_id')
    active_campaign = Campaign.query.get(active_campaign_id) if active_campaign_id else None
    return render_template('index.html', campaigns=campaigns, active_campaign=active_campaign)

@main_bp.route('/switch-campaign/<int:campaign_id>')
@login_required
def switch_campaign(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first_or_404()
    session['active_campaign_id'] = campaign.id
    return redirect(url_for('main.index'))