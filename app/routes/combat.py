from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_required
from app.models import Session as GameSession, PlayerCharacter, BestiaryEntry, Campaign

combat_bp = Blueprint('combat', __name__, url_prefix='/combat-tracker')


def get_active_campaign_id():
    return session.get('active_campaign_id')


@combat_bp.route('/')
@login_required
def tracker():
    campaign_id = get_active_campaign_id()

    if request.args.get('from') != 'session':
        session.pop('in_session_mode', None)
        session.pop('session_title', None)

    current_session_id = session.get('current_session_id')

    # Build list of sessions to populate the session picker dropdown
    all_sessions = []
    session_pcs = []
    current_session_name = None

    if campaign_id:
        campaign = Campaign.query.get(campaign_id)
        is_icrpg = 'icrpg' in (campaign.system or '').lower() if campaign else False

        all_sessions = GameSession.query.filter_by(campaign_id=campaign_id)\
            .order_by(GameSession.number.desc()).all()

        # If a session is active, collect attending PCs and their stats
        if current_session_id:
            game_session = GameSession.query.filter_by(
                id=current_session_id, campaign_id=campaign_id
            ).first()
            if game_session:
                num = f'#{game_session.number} ' if game_session.number else ''
                current_session_name = f"{num}{game_session.title or 'Untitled'}".strip()

                for attendance in game_session.attendances:
                    pc = attendance.character
                    if not pc:
                        continue

                    pc_data = {
                        'id': pc.id,
                        'character_name': pc.character_name,
                        'player_name': pc.player_name,
                    }

                    # ICRPG: pull stats from the ICRPG sheet
                    if is_icrpg and pc.icrpg_sheet:
                        s = pc.icrpg_sheet
                        pc_data['stats'] = {
                            'STR': s.total_stat('STR'),
                            'DEX': s.total_stat('DEX'),
                            'CON': s.total_stat('CON'),
                            'INT': s.total_stat('INT'),
                            'WIS': s.total_stat('WIS'),
                            'CHA': s.total_stat('CHA'),
                            'Defense': s.defense,
                        }
                        pc_data['hp_current'] = s.hp_current
                        pc_data['hp_max'] = s.hp_max
                    else:
                        # Generic campaign stats
                        pc_data['stats'] = {
                            st.template_field.stat_name: st.stat_value
                            for st in pc.stats if st.template_field
                        }

                    session_pcs.append(pc_data)

    # Build session monster data — Monster Instances linked to the current session.
    # These appear as a separate quick-add list in the modal.
    session_monsters = []
    if current_session_id and campaign_id:
        game_session = GameSession.query.filter_by(
            id=current_session_id, campaign_id=campaign_id
        ).first()
        if game_session:
            for inst in game_session.monsters_encountered:
                entry = inst.bestiary_entry
                session_monsters.append({
                    'id': inst.id,
                    'instance_name': inst.instance_name,
                    'status': inst.status,
                    'entry_name': entry.name,
                    'cr_level': entry.cr_level or '',
                    'stat_block': entry.stat_block or '',
                })

    # Build bestiary data for the quick-add dropdown.
    # Includes name, cr_level, and stat_block (for loading into monster notes).
    bestiary_data = [
        {
            'id': e.id,
            'name': e.name,
            'cr_level': e.cr_level or '',
            'stat_block': e.stat_block or '',
        }
        for e in BestiaryEntry.query.order_by(BestiaryEntry.name).all()
    ]

    return render_template(
        'combat/tracker.html',
        all_sessions=all_sessions,
        current_session_id=current_session_id,
        current_session_name=current_session_name,
        session_pcs=session_pcs,
        bestiary_data=bestiary_data,
        session_monsters=session_monsters,
    )


@combat_bp.route('/set-session', methods=['POST'])
@login_required
def set_session():
    """Store the chosen session ID in the Flask session so the combat tracker
    knows which PCs to offer for auto-population."""
    sess_id = request.form.get('session_id')
    if sess_id:
        session['current_session_id'] = int(sess_id)
    else:
        session.pop('current_session_id', None)
    in_session = session.get('in_session_mode')
    target = url_for('combat.tracker') + ('?from=session' if in_session else '')
    return redirect(target)
