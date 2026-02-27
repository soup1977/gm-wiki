from collections import defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from app import db
from app.models import Faction, NPC, Location, Quest

factions_bp = Blueprint('factions', __name__, url_prefix='/factions')

DISPOSITIONS = ['friendly', 'neutral', 'hostile', 'unknown']
DISPOSITION_COLORS = {
    'friendly': 'success',
    'neutral':  'secondary',
    'hostile':  'danger',
    'unknown':  'dark',
}


def get_active_campaign_id():
    return session.get('active_campaign_id')


@factions_bp.route('/')
@login_required
def list_factions():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    factions = (Faction.query
                .filter_by(campaign_id=campaign_id)
                .order_by(Faction.name)
                .all())

    groups = defaultdict(list)
    for f in factions:
        groups[f.disposition or 'unknown'].append(f)
    grouped = {d: groups[d] for d in DISPOSITIONS if groups[d]}

    return render_template('factions/list.html', factions=factions, grouped=grouped,
                           disposition_colors=DISPOSITION_COLORS)


@factions_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_faction():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Faction name is required.', 'danger')
            return render_template('factions/form.html', faction=None,
                                   dispositions=DISPOSITIONS)

        faction = Faction(
            campaign_id=campaign_id,
            name=name,
            description=request.form.get('description', '').strip() or None,
            disposition=request.form.get('disposition', 'unknown') or 'unknown',
            gm_notes=request.form.get('gm_notes', '').strip() or None,
        )
        db.session.add(faction)
        db.session.commit()
        flash(f'Faction "{faction.name}" created.', 'success')
        return redirect(url_for('factions.faction_detail', faction_id=faction.id))

    return render_template('factions/form.html', faction=None, dispositions=DISPOSITIONS)


@factions_bp.route('/<int:faction_id>')
@login_required
def faction_detail(faction_id):
    campaign_id = get_active_campaign_id()
    faction = Faction.query.filter_by(id=faction_id, campaign_id=campaign_id).first_or_404()
    return render_template('factions/detail.html', faction=faction,
                           disposition_colors=DISPOSITION_COLORS)


@factions_bp.route('/<int:faction_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_faction(faction_id):
    campaign_id = get_active_campaign_id()
    faction = Faction.query.filter_by(id=faction_id, campaign_id=campaign_id).first_or_404()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Faction name is required.', 'danger')
            return render_template('factions/form.html', faction=faction,
                                   dispositions=DISPOSITIONS)

        faction.name = name
        faction.description = request.form.get('description', '').strip() or None
        faction.disposition = request.form.get('disposition', 'unknown') or 'unknown'
        faction.gm_notes = request.form.get('gm_notes', '').strip() or None

        db.session.commit()
        flash(f'Faction "{faction.name}" updated.', 'success')
        return redirect(url_for('factions.faction_detail', faction_id=faction.id))

    return render_template('factions/form.html', faction=faction, dispositions=DISPOSITIONS)


@factions_bp.route('/<int:faction_id>/delete', methods=['POST'])
@login_required
def delete_faction(faction_id):
    campaign_id = get_active_campaign_id()
    faction = Faction.query.filter_by(id=faction_id, campaign_id=campaign_id).first_or_404()
    name = faction.name

    # Null out faction_id on all linked entities before deleting
    npc_count = len(faction.npcs)
    loc_count = len(faction.locations)
    quest_count = len(faction.quests)

    for npc in faction.npcs:
        npc.faction_id = None
    for loc in faction.locations:
        loc.faction_id = None
    for quest in faction.quests:
        quest.faction_id = None

    db.session.delete(faction)
    db.session.commit()

    msg = f'Faction "{name}" deleted.'
    unlinked = []
    if npc_count:
        unlinked.append(f'{npc_count} NPC(s)')
    if loc_count:
        unlinked.append(f'{loc_count} location(s)')
    if quest_count:
        unlinked.append(f'{quest_count} quest(s)')
    if unlinked:
        msg += f' Unlinked from: {", ".join(unlinked)}.'
    flash(msg, 'warning')
    return redirect(url_for('factions.list_factions'))
