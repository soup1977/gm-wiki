from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from app import db
from app.models import Campaign, Session, CompendiumEntry, Item, Quest, NPC, Location, CampaignStatTemplate

campaigns_bp = Blueprint('campaigns', __name__, url_prefix='/campaigns')

# Preset stat fields for common game systems.
# Shown as a dropdown on campaign create; GM can edit fields after creation.
STAT_PRESETS = {
    'none': {
        'name': 'None (add stats later)',
        'stats': []
    },
    'dnd5e': {
        'name': 'D&D 5e',
        'stats': [
            'Armor Class (AC)',
            'Max Hit Points',
            'Spell Save DC',
            'Passive Perception',
            'Passive Investigation',
            'Passive Insight',
        ]
    },
    'pathfinder2e': {
        'name': 'Pathfinder 2e',
        'stats': [
            'Armor Class (AC)',
            'Max Hit Points',
            'Perception',
            'Fortitude Save',
            'Reflex Save',
            'Will Save',
            'Class DC',
        ]
    },
    'icrpg': {
        'name': 'ICRPG',
        'stats': [
            'Armor',
            'Hearts (Max HP)',
            'Basic Effort',
            'Weapons/Tools Effort',
            'Magic Effort',
            'Ultimate Effort',
        ]
    },
    'custom': {
        'name': 'Custom (start blank)',
        'stats': []
    },
}


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
        db.session.flush()  # Assigns campaign.id before we create child records

        # Create stat template fields from the chosen preset
        preset_key = request.form.get('stat_preset', 'none')
        preset = STAT_PRESETS.get(preset_key, STAT_PRESETS['none'])
        for order, stat_name in enumerate(preset['stats']):
            field = CampaignStatTemplate(
                campaign_id=campaign.id,
                stat_name=stat_name,
                display_order=order
            )
            db.session.add(field)

        db.session.commit()

        # Auto-switch to the newly created campaign
        session['active_campaign_id'] = campaign.id
        flash(f'Campaign "{campaign.name}" created!', 'success')
        return redirect(url_for('main.index'))

    return render_template('campaigns/create.html', stat_presets=STAT_PRESETS)


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

    stat_fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()
    return render_template('campaigns/edit.html', campaign=campaign, stat_fields=stat_fields)


# ── Stat template management ─────────────────────────────────────────────────

@campaigns_bp.route('/<int:campaign_id>/stats/add', methods=['POST'])
def add_stat_field(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    stat_name = request.form.get('stat_name', '').strip()
    if not stat_name:
        flash('Stat name cannot be empty.', 'danger')
        return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id))

    # Place new field at the end
    last = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order.desc()).first()
    next_order = (last.display_order + 1) if last else 0

    field = CampaignStatTemplate(
        campaign_id=campaign_id,
        stat_name=stat_name,
        display_order=next_order
    )
    db.session.add(field)
    db.session.commit()
    flash(f'Stat field "{stat_name}" added.', 'success')
    return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')


@campaigns_bp.route('/<int:campaign_id>/stats/<int:stat_id>/rename', methods=['POST'])
def rename_stat_field(campaign_id, stat_id):
    field = CampaignStatTemplate.query.filter_by(id=stat_id, campaign_id=campaign_id).first_or_404()
    new_name = request.form.get('stat_name', '').strip()
    if not new_name:
        flash('Stat name cannot be empty.', 'danger')
    else:
        field.stat_name = new_name
        db.session.commit()
        flash('Stat field renamed.', 'success')
    return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')


@campaigns_bp.route('/<int:campaign_id>/stats/<int:stat_id>/delete', methods=['POST'])
def delete_stat_field(campaign_id, stat_id):
    field = CampaignStatTemplate.query.filter_by(id=stat_id, campaign_id=campaign_id).first_or_404()
    name = field.stat_name
    db.session.delete(field)
    db.session.commit()
    flash(f'Stat field "{name}" deleted.', 'warning')
    return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')


@campaigns_bp.route('/<int:campaign_id>/stats/<int:stat_id>/move', methods=['POST'])
def move_stat_field(campaign_id, stat_id):
    direction = request.form.get('direction')  # 'up' or 'down'
    field = CampaignStatTemplate.query.filter_by(id=stat_id, campaign_id=campaign_id).first_or_404()

    fields = CampaignStatTemplate.query.filter_by(campaign_id=campaign_id)\
        .order_by(CampaignStatTemplate.display_order).all()

    idx = next((i for i, f in enumerate(fields) if f.id == stat_id), None)
    if idx is None:
        return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')

    if direction == 'up' and idx > 0:
        swap = fields[idx - 1]
        field.display_order, swap.display_order = swap.display_order, field.display_order
        db.session.commit()
    elif direction == 'down' and idx < len(fields) - 1:
        swap = fields[idx + 1]
        field.display_order, swap.display_order = swap.display_order, field.display_order
        db.session.commit()

    return redirect(url_for('campaigns.edit_campaign', campaign_id=campaign_id) + '#stat-template')


# ── Delete campaign ───────────────────────────────────────────────────────────

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

    # Stat template fields are standalone per campaign.
    for field in list(campaign.stat_template_fields):
        db.session.delete(field)

    db.session.delete(campaign)
    db.session.commit()

    flash(f'Campaign "{name}" and all its content deleted.', 'warning')
    return redirect(url_for('campaigns.list_campaigns'))
