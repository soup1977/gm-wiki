from flask import Blueprint, render_template, session, redirect, url_for
from app.models import Campaign

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    campaigns = Campaign.query.order_by(Campaign.name).all()
    # 'session' here is Flask's browser session (like a cookie), not a game session
    active_campaign_id = session.get('active_campaign_id')
    active_campaign = Campaign.query.get(active_campaign_id) if active_campaign_id else None
    return render_template('index.html', campaigns=campaigns, active_campaign=active_campaign)

@main_bp.route('/switch-campaign/<int:campaign_id>')
def switch_campaign(campaign_id):
    # Store the chosen campaign ID in the browser session cookie
    session['active_campaign_id'] = campaign_id
    return redirect(url_for('main.index'))