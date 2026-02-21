from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from app import db
from app.models import Campaign

campaigns_bp = Blueprint('campaigns', __name__, url_prefix='/campaigns')

@campaigns_bp.route('/')
def list_campaigns():
    campaigns = Campaign.query.order_by(Campaign.name).all()
    return render_template('campaigns/list.html', campaigns=campaigns)

@campaigns_bp.route('/create', methods=['GET', 'POST'])
def create_campaign():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Campaign name is required.', 'danger')
            return redirect(url_for('campaigns.create_campaign'))
        
        campaign = Campaign(
            name=name,
            system=request.form.get('system', '').strip(),
            status=request.form.get('status', 'active'),
            description=request.form.get('description', '').strip()
        )
        db.session.add(campaign)
        db.session.commit()
        
        # Auto-switch to the newly created campaign
        session['active_campaign_id'] = campaign.id
        flash(f'Campaign "{campaign.name}" created!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('campaigns/create.html')

@campaigns_bp.route('/<int:campaign_id>')
def campaign_detail(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    return render_template('campaigns/detail.html', campaign=campaign)

@campaigns_bp.route('/<int:campaign_id>/delete', methods=['POST'])
def delete_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    db.session.delete(campaign)
    db.session.commit()
    flash(f'Campaign "{campaign.name}" deleted.', 'warning')
    return redirect(url_for('campaigns.list_campaigns'))