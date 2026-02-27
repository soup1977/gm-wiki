import re
from collections import defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import (Encounter, EncounterMonster, BestiaryEntry,
                        MonsterInstance, RandomTable, Session as GameSession)

encounters_bp = Blueprint('encounters', __name__, url_prefix='/encounters')

ENCOUNTER_TYPES = ['combat', 'loot', 'social', 'trap', 'other']
ENCOUNTER_STATUSES = ['planned', 'used', 'skipped']
# Display order for grouped list
STATUS_ORDER = ['planned', 'used', 'skipped']

TYPE_COLORS = {
    'combat':  'danger',
    'loot':    'success',
    'social':  'info',
    'trap':    'warning',
    'other':   'secondary',
}


def get_active_campaign_id():
    return session.get('active_campaign_id')


def _auto_instance_name(entry, campaign_id):
    """Generate next sequential instance name. E.g. 'Goblin 3' if 1 and 2 exist."""
    existing = MonsterInstance.query.filter_by(
        bestiary_entry_id=entry.id,
        campaign_id=campaign_id
    ).all()

    if not existing:
        return f"{entry.name} 1"

    highest = 0
    for inst in existing:
        match = re.search(r'(\d+)$', inst.instance_name)
        if match:
            num = int(match.group(1))
            if num > highest:
                highest = num

    return f"{entry.name} {highest + 1}"


def _save_monsters(encounter, entry_ids, counts):
    """Replace all EncounterMonster rows for this encounter from parallel lists."""
    # cascade='all, delete-orphan' handles removal automatically when we reassign
    new_monsters = []
    for eid, cnt in zip(entry_ids, counts):
        eid = eid.strip()
        if not eid:
            continue
        try:
            cnt = max(1, int(cnt))
        except (ValueError, TypeError):
            cnt = 1
        entry = BestiaryEntry.query.get(int(eid))
        if entry:
            new_monsters.append(EncounterMonster(
                bestiary_entry_id=entry.id,
                count=cnt,
            ))
    encounter.monsters = new_monsters


@encounters_bp.route('/')
def list_encounters():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    encounters = (Encounter.query
                  .filter_by(campaign_id=campaign_id)
                  .order_by(Encounter.name)
                  .all())

    groups = defaultdict(list)
    for enc in encounters:
        groups[enc.status or 'planned'].append(enc)
    grouped = {s: groups[s] for s in STATUS_ORDER if groups[s]}

    return render_template('encounters/list.html',
                           encounters=encounters,
                           grouped=grouped,
                           type_colors=TYPE_COLORS)


@encounters_bp.route('/new', methods=['GET', 'POST'])
def create_encounter():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    sessions = (GameSession.query
                .filter_by(campaign_id=campaign_id)
                .order_by(GameSession.number.desc())
                .all())
    bestiary_entries = BestiaryEntry.query.order_by(BestiaryEntry.name).all()
    random_tables = RandomTable.query.filter_by(campaign_id=campaign_id).order_by(RandomTable.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Encounter name is required.', 'danger')
            return render_template('encounters/form.html', encounter=None,
                                   sessions=sessions, bestiary_entries=bestiary_entries,
                                   random_tables=random_tables,
                                   encounter_types=ENCOUNTER_TYPES,
                                   encounter_statuses=ENCOUNTER_STATUSES,
                                   type_colors=TYPE_COLORS)

        sess_id = request.form.get('session_id', '').strip() or None
        table_id = request.form.get('loot_table_id', '').strip() or None

        encounter = Encounter(
            campaign_id=campaign_id,
            name=name,
            encounter_type=request.form.get('encounter_type', 'combat'),
            status=request.form.get('status', 'planned'),
            description=request.form.get('description', '').strip() or None,
            gm_notes=request.form.get('gm_notes', '').strip() or None,
            session_id=int(sess_id) if sess_id else None,
            loot_table_id=int(table_id) if table_id else None,
        )
        db.session.add(encounter)
        db.session.flush()

        entry_ids = request.form.getlist('monster_entry_ids[]')
        counts = request.form.getlist('monster_counts[]')
        _save_monsters(encounter, entry_ids, counts)

        db.session.commit()
        flash(f'Encounter "{encounter.name}" created.', 'success')
        return redirect(url_for('encounters.encounter_detail', encounter_id=encounter.id))

    return render_template('encounters/form.html', encounter=None,
                           sessions=sessions, bestiary_entries=bestiary_entries,
                           random_tables=random_tables,
                           encounter_types=ENCOUNTER_TYPES,
                           encounter_statuses=ENCOUNTER_STATUSES,
                           type_colors=TYPE_COLORS)


@encounters_bp.route('/<int:encounter_id>')
def encounter_detail(encounter_id):
    campaign_id = get_active_campaign_id()
    encounter = Encounter.query.filter_by(id=encounter_id, campaign_id=campaign_id).first_or_404()
    return render_template('encounters/detail.html', encounter=encounter,
                           type_colors=TYPE_COLORS)


@encounters_bp.route('/<int:encounter_id>/edit', methods=['GET', 'POST'])
def edit_encounter(encounter_id):
    campaign_id = get_active_campaign_id()
    encounter = Encounter.query.filter_by(id=encounter_id, campaign_id=campaign_id).first_or_404()

    sessions = (GameSession.query
                .filter_by(campaign_id=campaign_id)
                .order_by(GameSession.number.desc())
                .all())
    bestiary_entries = BestiaryEntry.query.order_by(BestiaryEntry.name).all()
    random_tables = RandomTable.query.filter_by(campaign_id=campaign_id).order_by(RandomTable.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Encounter name is required.', 'danger')
            return render_template('encounters/form.html', encounter=encounter,
                                   sessions=sessions, bestiary_entries=bestiary_entries,
                                   random_tables=random_tables,
                                   encounter_types=ENCOUNTER_TYPES,
                                   encounter_statuses=ENCOUNTER_STATUSES,
                                   type_colors=TYPE_COLORS)

        sess_id = request.form.get('session_id', '').strip() or None
        table_id = request.form.get('loot_table_id', '').strip() or None

        encounter.name = name
        encounter.encounter_type = request.form.get('encounter_type', 'combat')
        encounter.status = request.form.get('status', 'planned')
        encounter.description = request.form.get('description', '').strip() or None
        encounter.gm_notes = request.form.get('gm_notes', '').strip() or None
        encounter.session_id = int(sess_id) if sess_id else None
        encounter.loot_table_id = int(table_id) if table_id else None

        entry_ids = request.form.getlist('monster_entry_ids[]')
        counts = request.form.getlist('monster_counts[]')
        _save_monsters(encounter, entry_ids, counts)

        db.session.commit()
        flash(f'Encounter "{encounter.name}" updated.', 'success')
        return redirect(url_for('encounters.encounter_detail', encounter_id=encounter.id))

    return render_template('encounters/form.html', encounter=encounter,
                           sessions=sessions, bestiary_entries=bestiary_entries,
                           random_tables=random_tables,
                           encounter_types=ENCOUNTER_TYPES,
                           encounter_statuses=ENCOUNTER_STATUSES,
                           type_colors=TYPE_COLORS)


@encounters_bp.route('/<int:encounter_id>/delete', methods=['POST'])
def delete_encounter(encounter_id):
    campaign_id = get_active_campaign_id()
    encounter = Encounter.query.filter_by(id=encounter_id, campaign_id=campaign_id).first_or_404()
    name = encounter.name
    db.session.delete(encounter)
    db.session.commit()
    flash(f'Encounter "{name}" deleted.', 'success')
    return redirect(url_for('encounters.list_encounters'))


@encounters_bp.route('/<int:encounter_id>/start-combat', methods=['POST'])
def start_combat(encounter_id):
    """Spawn MonsterInstances for each EncounterMonster and send the GM to the combat tracker."""
    campaign_id = get_active_campaign_id()
    encounter = Encounter.query.filter_by(id=encounter_id, campaign_id=campaign_id).first_or_404()

    current_session_id = session.get('current_session_id')
    if not current_session_id:
        flash('Start a session in Session Mode before launching combat.', 'warning')
        return redirect(url_for('encounters.encounter_detail', encounter_id=encounter_id))

    game_session = GameSession.query.filter_by(
        id=current_session_id, campaign_id=campaign_id
    ).first()
    if not game_session:
        flash('Active session not found. Please re-select it in Session Mode.', 'warning')
        return redirect(url_for('encounters.encounter_detail', encounter_id=encounter_id))

    spawned = 0
    for em in encounter.monsters:
        entry = em.bestiary_entry
        for _ in range(em.count):
            inst = MonsterInstance(
                bestiary_entry_id=entry.id,
                campaign_id=campaign_id,
                instance_name=_auto_instance_name(entry, campaign_id),
                status='alive',
            )
            db.session.add(inst)
            db.session.flush()  # get inst.id so _auto_instance_name sees it next iteration
            game_session.monsters_encountered.append(inst)
            spawned += 1

    encounter.status = 'used'
    db.session.commit()

    flash(f'Spawned {spawned} creature(s) from "{encounter.name}". Go get \'em!', 'success')
    return redirect(url_for('combat.tracker') + '?from=session')
