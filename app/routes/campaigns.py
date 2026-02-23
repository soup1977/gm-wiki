from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from app import db
from app.models import Campaign, Session, CompendiumEntry, Item, Quest, NPC, Location

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

@campaigns_bp.route('/<int:campaign_id>/edit', methods=['GET', 'POST'])
def edit_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Campaign name is required.', 'danger')
            return render_template('campaigns/edit.html', campaign=campaign)
        campaign.name = name
        campaign.system = request.form.get('system', '').strip()
        campaign.status = request.form.get('status', 'active')
        campaign.description = request.form.get('description', '').strip()
        db.session.commit()
        flash(f'Campaign "{campaign.name}" updated.', 'success')
        return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign.id))
    return render_template('campaigns/edit.html', campaign=campaign)


@campaigns_bp.route('/<int:campaign_id>/delete', methods=['POST'])
def delete_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    name = campaign.name

    # Delete in dependency order so nothing is left referencing a deleted object.
    # Sessions link to NPCs/Locations/Items/Quests — delete first.
    for sess in list(campaign.sessions):
        db.session.delete(sess)

    # Compendium entries are standalone.
    for entry in list(campaign.compendium_entries):
        db.session.delete(entry)

    # Items reference NPCs and Locations via nullable FKs — nullify then delete.
    for item in list(campaign.items):
        item.owner_npc_id = None
        item.origin_location_id = None
        db.session.delete(item)

    # Quests link to NPCs and Locations — clear links then delete.
    for quest in list(campaign.quests):
        quest.involved_npcs = []
        quest.involved_locations = []
        db.session.delete(quest)

    # NPCs reference Locations via home_location_id — nullify then delete.
    for npc in list(campaign.npcs):
        npc.home_location_id = None
        npc.connected_locations = []
        db.session.delete(npc)

    # Locations are last — nullify parent refs first to avoid self-referential errors.
    for loc in list(campaign.locations):
        loc.parent_location_id = None
    db.session.flush()
    for loc in list(campaign.locations):
        loc.connected_locations = []
        db.session.delete(loc)

    db.session.delete(campaign)
    db.session.commit()

    flash(f'Campaign "{name}" and all its content deleted.', 'warning')
    return redirect(url_for('campaigns.list_campaigns'))