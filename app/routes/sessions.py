from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import Session, NPC, Location, Item, Quest

sessions_bp = Blueprint('sessions', __name__)


def get_active_campaign_id():
    return session.get('active_campaign_id')


@sessions_bp.route('/sessions')
def list_sessions():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))
    sessions_list = (Session.query
                     .filter_by(campaign_id=campaign_id)
                     .order_by(Session.number.desc())
                     .all())
    return render_template('sessions/list.html', sessions=sessions_list)


@sessions_bp.route('/sessions/new', methods=['GET', 'POST'])
def create_session():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    items = Item.query.filter_by(campaign_id=campaign_id).order_by(Item.name).all()
    quests = Quest.query.filter_by(campaign_id=campaign_id).order_by(Quest.name).all()

    if request.method == 'POST':
        date_str = request.form.get('date_played', '').strip()
        parsed_date = None
        if date_str:
            try:
                parsed_date = date.fromisoformat(date_str)
            except ValueError:
                flash('Invalid date format. Use YYYY-MM-DD.', 'danger')
                return render_template('sessions/form.html', sess=None,
                                       npcs=npcs, locations=locations,
                                       items=items, quests=quests)

        sess = Session(
            campaign_id=campaign_id,
            number=request.form.get('number') or None,
            title=request.form.get('title', '').strip() or None,
            date_played=parsed_date,
            summary=request.form.get('summary', '').strip() or None,
            gm_notes=request.form.get('gm_notes', '').strip() or None,
        )

        sess.npcs_featured = NPC.query.filter(
            NPC.id.in_(request.form.getlist('npcs_featured')),
            NPC.campaign_id == campaign_id
        ).all()
        sess.locations_visited = Location.query.filter(
            Location.id.in_(request.form.getlist('locations_visited')),
            Location.campaign_id == campaign_id
        ).all()
        sess.items_mentioned = Item.query.filter(
            Item.id.in_(request.form.getlist('items_mentioned')),
            Item.campaign_id == campaign_id
        ).all()
        sess.quests_touched = Quest.query.filter(
            Quest.id.in_(request.form.getlist('quests_touched')),
            Quest.campaign_id == campaign_id
        ).all()

        db.session.add(sess)
        db.session.commit()
        label = f'Session {sess.number}' if sess.number else 'Session'
        flash(f'{label} created.', 'success')
        return redirect(url_for('sessions.session_detail', session_id=sess.id))

    return render_template('sessions/form.html', sess=None,
                           npcs=npcs, locations=locations,
                           items=items, quests=quests)


@sessions_bp.route('/sessions/<int:session_id>')
def session_detail(session_id):
    campaign_id = get_active_campaign_id()
    sess = Session.query.filter_by(id=session_id, campaign_id=campaign_id).first_or_404()
    return render_template('sessions/detail.html', sess=sess)


@sessions_bp.route('/sessions/<int:session_id>/edit', methods=['GET', 'POST'])
def edit_session(session_id):
    campaign_id = get_active_campaign_id()
    sess = Session.query.filter_by(id=session_id, campaign_id=campaign_id).first_or_404()

    npcs = NPC.query.filter_by(campaign_id=campaign_id).order_by(NPC.name).all()
    locations = Location.query.filter_by(campaign_id=campaign_id).order_by(Location.name).all()
    items = Item.query.filter_by(campaign_id=campaign_id).order_by(Item.name).all()
    quests = Quest.query.filter_by(campaign_id=campaign_id).order_by(Quest.name).all()

    if request.method == 'POST':
        date_str = request.form.get('date_played', '').strip()
        parsed_date = None
        if date_str:
            try:
                parsed_date = date.fromisoformat(date_str)
            except ValueError:
                flash('Invalid date format. Use YYYY-MM-DD.', 'danger')
                return render_template('sessions/form.html', sess=sess,
                                       npcs=npcs, locations=locations,
                                       items=items, quests=quests)

        sess.number = request.form.get('number') or None
        sess.title = request.form.get('title', '').strip() or None
        sess.date_played = parsed_date
        sess.summary = request.form.get('summary', '').strip() or None
        sess.gm_notes = request.form.get('gm_notes', '').strip() or None

        sess.npcs_featured = NPC.query.filter(
            NPC.id.in_(request.form.getlist('npcs_featured')),
            NPC.campaign_id == campaign_id
        ).all()
        sess.locations_visited = Location.query.filter(
            Location.id.in_(request.form.getlist('locations_visited')),
            Location.campaign_id == campaign_id
        ).all()
        sess.items_mentioned = Item.query.filter(
            Item.id.in_(request.form.getlist('items_mentioned')),
            Item.campaign_id == campaign_id
        ).all()
        sess.quests_touched = Quest.query.filter(
            Quest.id.in_(request.form.getlist('quests_touched')),
            Quest.campaign_id == campaign_id
        ).all()

        db.session.commit()
        flash('Session updated.', 'success')
        return redirect(url_for('sessions.session_detail', session_id=sess.id))

    return render_template('sessions/form.html', sess=sess,
                           npcs=npcs, locations=locations,
                           items=items, quests=quests)


@sessions_bp.route('/sessions/<int:session_id>/delete', methods=['POST'])
def delete_session(session_id):
    campaign_id = get_active_campaign_id()
    sess = Session.query.filter_by(id=session_id, campaign_id=campaign_id).first_or_404()
    label = f'Session {sess.number}' if sess.number else 'Session'
    db.session.delete(sess)
    db.session.commit()
    flash(f'{label} deleted.', 'success')
    return redirect(url_for('sessions.list_sessions'))
