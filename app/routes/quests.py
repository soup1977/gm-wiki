from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Quest, NPC, Location

quests_bp = Blueprint('quests', __name__)

QUEST_STATUSES = ['active', 'completed', 'failed', 'on_hold']


def get_active_campaign_id():
    return session.get('active_campaign_id')


@quests_bp.route('/quests')
def list_quests():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))
    quests = Quest.query.filter_by(campaign_id=campaign_id).order_by(Quest.name).all()
    return render_template('quests/list.html', quests=quests)


@quests_bp.route('/quests/new', methods=['GET', 'POST'])
def create_quest():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Quest name is required.', 'danger')
            return render_template('quests/form.html', quest=None,
                                   npcs=npcs, locations=locations,
                                   statuses=QUEST_STATUSES)

        quest = Quest(
            campaign_id=campaign_id,
            name=name,
            status=request.form.get('status', 'active'),
            hook=request.form.get('hook', '').strip() or None,
            description=request.form.get('description', '').strip() or None,
            outcome=request.form.get('outcome', '').strip() or None,
            gm_notes=request.form.get('gm_notes', '').strip() or None,
        )

        # Many-to-many: involved NPCs
        selected_npc_ids = request.form.getlist('involved_npcs')
        quest.involved_npcs = NPC.query.filter(
            NPC.id.in_(selected_npc_ids), NPC.campaign_id == campaign_id
        ).all()

        # Many-to-many: involved Locations
        selected_location_ids = request.form.getlist('involved_locations')
        quest.involved_locations = Location.query.filter(
            Location.id.in_(selected_location_ids), Location.campaign_id == campaign_id
        ).all()

        db.session.add(quest)
        db.session.commit()
        flash(f'Quest "{quest.name}" created.', 'success')
        return redirect(url_for('quests.quest_detail', quest_id=quest.id))

    return render_template('quests/form.html', quest=None,
                           npcs=npcs, locations=locations,
                           statuses=QUEST_STATUSES)


@quests_bp.route('/quests/<int:quest_id>')
def quest_detail(quest_id):
    campaign_id = get_active_campaign_id()
    quest = Quest.query.filter_by(id=quest_id, campaign_id=campaign_id).first_or_404()
    return render_template('quests/detail.html', quest=quest)


@quests_bp.route('/quests/<int:quest_id>/edit', methods=['GET', 'POST'])
def edit_quest(quest_id):
    campaign_id = get_active_campaign_id()
    quest = Quest.query.filter_by(id=quest_id, campaign_id=campaign_id).first_or_404()

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Quest name is required.', 'danger')
            return render_template('quests/form.html', quest=quest,
                                   npcs=npcs, locations=locations,
                                   statuses=QUEST_STATUSES)

        quest.name = name
        quest.status = request.form.get('status', 'active')
        quest.hook = request.form.get('hook', '').strip() or None
        quest.description = request.form.get('description', '').strip() or None
        quest.outcome = request.form.get('outcome', '').strip() or None
        quest.gm_notes = request.form.get('gm_notes', '').strip() or None

        selected_npc_ids = request.form.getlist('involved_npcs')
        quest.involved_npcs = NPC.query.filter(
            NPC.id.in_(selected_npc_ids), NPC.campaign_id == campaign_id
        ).all()

        selected_location_ids = request.form.getlist('involved_locations')
        quest.involved_locations = Location.query.filter(
            Location.id.in_(selected_location_ids), Location.campaign_id == campaign_id
        ).all()

        db.session.commit()
        flash(f'Quest "{quest.name}" updated.', 'success')
        return redirect(url_for('quests.quest_detail', quest_id=quest.id))

    return render_template('quests/form.html', quest=quest,
                           npcs=npcs, locations=locations,
                           statuses=QUEST_STATUSES)


@quests_bp.route('/quests/<int:quest_id>/delete', methods=['POST'])
def delete_quest(quest_id):
    campaign_id = get_active_campaign_id()
    quest = Quest.query.filter_by(id=quest_id, campaign_id=campaign_id).first_or_404()
    name = quest.name
    db.session.delete(quest)
    db.session.commit()
    flash(f'Quest "{name}" deleted.', 'success')
    return redirect(url_for('quests.list_quests'))
