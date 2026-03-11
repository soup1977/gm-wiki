from datetime import date
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, session, jsonify)
from flask_login import login_required, current_user
from app import db
from app.models import (Campaign, Adventure, AdventureAct, AdventureScene,
                        AdventureRoom, RoomCreature, RoomLoot, RoomHazard,
                        AdventureRoomLog, RoomNPC, NPC, Faction, BestiaryEntry,
                        Location, Quest, Item, Encounter, Session as GameSession,
                        RandomTable, PlayerCharacter)

adventures_bp = Blueprint('adventures', __name__, url_prefix='/adventures')


def _get_active_campaign():
    """Return the active Campaign or None."""
    cid = session.get('active_campaign_id')
    if not cid:
        return None
    return Campaign.query.get(cid)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@adventures_bp.route('/')
@login_required
def list_adventures():
    campaign = _get_active_campaign()
    if not campaign:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    adventures = (Adventure.query
                  .filter_by(campaign_id=campaign.id)
                  .order_by(Adventure.created_at.desc())
                  .all())
    return render_template('adventures/list.html',
                           campaign=campaign,
                           adventures=adventures)


# ---------------------------------------------------------------------------
# Create (concept input page)
# ---------------------------------------------------------------------------

@adventures_bp.route('/create')
@login_required
def create():
    campaign = _get_active_campaign()
    if not campaign:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('main.index'))
    return render_template('adventures/create.html', campaign=campaign)


# ---------------------------------------------------------------------------
# Draft Review (AI draft displayed for editing before save)
# ---------------------------------------------------------------------------

@adventures_bp.route('/draft')
@login_required
def draft_review():
    """Render the draft review page. The AI draft JSON is passed from the
    create page via sessionStorage (JS-side), so this route just renders
    the shell template and the JS fills it in."""
    campaign = _get_active_campaign()
    if not campaign:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('main.index'))
    return render_template('adventures/draft_review.html', campaign=campaign)


# ---------------------------------------------------------------------------
# Save (POST from draft review — creates all DB records)
# ---------------------------------------------------------------------------

@adventures_bp.route('/save', methods=['POST'])
@login_required
def save():
    """Accept the full adventure JSON from the draft review page and
    create all DB records (Adventure, Acts, Scenes, Rooms, Creatures, Loot)."""
    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400

    try:
        adventure = Adventure(
            campaign_id=campaign.id,
            name=data.get('title', 'Untitled Adventure'),
            tagline=data.get('tagline', ''),
            concept=data.get('concept', ''),
            synopsis=data.get('synopsis', ''),
            hook=data.get('hook', ''),
            premise=data.get('premise', ''),
            system_hint=data.get('system_hint', 'generic'),
            status='Draft',
        )
        db.session.add(adventure)
        db.session.flush()  # get adventure.id before children

        for act_idx, act_data in enumerate(data.get('acts', [])):
            act = AdventureAct(
                adventure_id=adventure.id,
                number=act_data.get('number', act_idx + 1),
                title=act_data.get('title', f'Act {act_idx + 1}'),
                description=act_data.get('description', ''),
                sort_order=act_idx,
            )
            db.session.add(act)
            db.session.flush()

            for scene_idx, scene_data in enumerate(act_data.get('scenes', [])):
                scene = AdventureScene(
                    act_id=act.id,
                    title=scene_data.get('title', 'Unnamed Scene'),
                    description=scene_data.get('description', ''),
                    scene_type=scene_data.get('scene_type', ''),
                    sort_order=scene_idx,
                )
                db.session.add(scene)
                db.session.flush()

                for room_idx, room_data in enumerate(scene_data.get('rooms', [])):
                    room = AdventureRoom(
                        scene_id=scene.id,
                        key=room_data.get('key', ''),
                        title=room_data.get('title', 'Unnamed Room'),
                        read_aloud=room_data.get('read_aloud', ''),
                        gm_notes=room_data.get('gm_notes', ''),
                        sort_order=room_idx,
                    )
                    db.session.add(room)
                    db.session.flush()

                    for c_data in room_data.get('creatures', []):
                        creature = RoomCreature(
                            room_id=room.id,
                            name=c_data.get('name', 'Unknown Creature'),
                            hearts=c_data.get('hearts', 1),
                            effort_type=c_data.get('effort_type', ''),
                            special_move=c_data.get('special_move', ''),
                            timer_rounds=c_data.get('timer_rounds'),
                            hp=c_data.get('hp'),
                            ac=c_data.get('ac'),
                            cr=c_data.get('cr', ''),
                            actions=c_data.get('actions', ''),
                        )
                        db.session.add(creature)

                    for l_data in room_data.get('loot', []):
                        loot = RoomLoot(
                            room_id=room.id,
                            name=l_data.get('name', 'Unknown Loot'),
                            description=l_data.get('description', ''),
                        )
                        db.session.add(loot)

                    for h_data in room_data.get('hazards', []):
                        hazard = RoomHazard(
                            room_id=room.id,
                            name=h_data.get('name', 'Unknown Hazard'),
                            description=h_data.get('description', ''),
                            dc_or_target=h_data.get('dc_or_target', ''),
                            consequence=h_data.get('consequence', ''),
                        )
                        db.session.add(hazard)

        # Create quests from AI-generated stubs (only those the GM chose to include)
        for q_data in data.get('quests', []):
            scope = q_data.get('scope', 'adventure')
            quest = Quest(
                campaign_id=campaign.id,
                name=q_data.get('name', 'Unnamed Quest'),
                hook=q_data.get('hook', ''),
                status=q_data.get('status', 'Active'),
                adventure_id=adventure.id if scope == 'adventure' else None,
            )
            db.session.add(quest)
            db.session.flush()
            if scope == 'campaign':
                adventure.campaign_quests.append(quest)

        db.session.commit()
        return jsonify({'success': True, 'adventure_id': adventure.id,
                        'redirect': url_for('adventures.detail', adventure_id=adventure.id) + '#tab-structure'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@adventures_bp.route('/<int:adventure_id>')
@login_required
def detail(adventure_id):
    adventure = Adventure.query.get_or_404(adventure_id)
    campaign = _get_active_campaign()
    # Linked entities for Entities tab
    linked_npcs      = NPC.query.filter_by(adventure_id=adventure_id).all()
    featured_npcs    = adventure.key_npcs  # M-to-M campaign NPCs featured in this adventure
    linked_locations = Location.query.filter_by(adventure_id=adventure_id).all()
    linked_quests    = Quest.query.filter_by(adventure_id=adventure_id).all()
    linked_items     = Item.query.filter_by(adventure_id=adventure_id).all()
    campaign_quests  = adventure.campaign_quests
    # All campaign entities for "link existing" dropdowns
    all_npcs      = NPC.query.filter_by(campaign_id=campaign.id).order_by(NPC.name).all() if campaign else []
    all_locations = Location.query.filter_by(campaign_id=campaign.id).order_by(Location.name).all() if campaign else []
    all_quests    = Quest.query.filter_by(campaign_id=campaign.id).order_by(Quest.name).all() if campaign else []
    # Campaign-wide quests (no adventure_id) available for M-to-M linking
    all_campaign_quests = Quest.query.filter_by(campaign_id=campaign.id, adventure_id=None).order_by(Quest.name).all() if campaign else []
    all_items     = Item.query.filter_by(campaign_id=campaign.id).order_by(Item.name).all() if campaign else []
    return render_template('adventures/detail.html',
                           adventure=adventure,
                           campaign=campaign,
                           linked_npcs=linked_npcs,
                           featured_npcs=featured_npcs,
                           linked_locations=linked_locations,
                           linked_quests=linked_quests,
                           campaign_quests=campaign_quests,
                           linked_items=linked_items,
                           all_npcs=all_npcs,
                           all_locations=all_locations,
                           all_quests=all_quests,
                           all_campaign_quests=all_campaign_quests,
                           all_items=all_items)


# ---------------------------------------------------------------------------
# Edit (metadata only — name, tagline, synopsis, hook, premise, system_hint)
# ---------------------------------------------------------------------------

@adventures_bp.route('/<int:adventure_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(adventure_id):
    adventure = Adventure.query.get_or_404(adventure_id)
    campaign = _get_active_campaign()

    if request.method == 'POST':
        adventure.name = request.form.get('name', adventure.name).strip()
        adventure.tagline = request.form.get('tagline', '').strip()
        adventure.synopsis = request.form.get('synopsis', '').strip()
        adventure.hook = request.form.get('hook', '').strip()
        adventure.premise = request.form.get('premise', '').strip()
        adventure.system_hint = request.form.get('system_hint', 'generic')
        adventure.status = request.form.get('status', adventure.status)
        adventure.planning_notes = request.form.get('planning_notes', '').strip()
        db.session.commit()
        flash(f'"{adventure.name}" updated.', 'success')
        return redirect(url_for('adventures.detail', adventure_id=adventure.id))

    return render_template('adventures/edit.html',
                           adventure=adventure,
                           campaign=campaign)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@adventures_bp.route('/<int:adventure_id>/delete', methods=['POST'])
@login_required
def delete(adventure_id):
    adventure = Adventure.query.get_or_404(adventure_id)
    name = adventure.name
    db.session.delete(adventure)
    db.session.commit()
    flash(f'"{name}" deleted.', 'success')
    return redirect(url_for('adventures.list_adventures'))


# ---------------------------------------------------------------------------
# Room edit (GET shows form, POST saves changes)
# ---------------------------------------------------------------------------

@adventures_bp.route('/rooms/<int:room_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    room = AdventureRoom.query.get_or_404(room_id)
    adventure = room.scene.act.adventure
    campaign = _get_active_campaign()

    if request.method == 'POST':
        room.key = request.form.get('key', room.key or '').strip()
        room.title = request.form.get('title', room.title).strip()
        room.read_aloud = request.form.get('read_aloud', '').strip()
        room.gm_notes = request.form.get('gm_notes', '').strip()

        # Replace creatures
        for c in room.creatures:
            db.session.delete(c)
        names = request.form.getlist('creature_name')
        hearts_list = request.form.getlist('creature_hearts')
        effort_list = request.form.getlist('creature_effort')
        move_list = request.form.getlist('creature_move')
        hp_list = request.form.getlist('creature_hp')
        ac_list = request.form.getlist('creature_ac')
        cr_list = request.form.getlist('creature_cr')
        for i, name in enumerate(names):
            if not name.strip():
                continue
            c = RoomCreature(
                room_id=room.id,
                name=name.strip(),
                hearts=int(hearts_list[i]) if i < len(hearts_list) and hearts_list[i] else 1,
                effort_type=effort_list[i] if i < len(effort_list) else '',
                special_move=move_list[i] if i < len(move_list) else '',
                hp=int(hp_list[i]) if i < len(hp_list) and hp_list[i] else None,
                ac=int(ac_list[i]) if i < len(ac_list) and ac_list[i] else None,
                cr=cr_list[i] if i < len(cr_list) else '',
            )
            db.session.add(c)

        # Replace loot
        for l in room.loot:
            db.session.delete(l)
        loot_names = request.form.getlist('loot_name')
        loot_descs = request.form.getlist('loot_desc')
        for i, name in enumerate(loot_names):
            if not name.strip():
                continue
            l = RoomLoot(
                room_id=room.id,
                name=name.strip(),
                description=loot_descs[i] if i < len(loot_descs) else '',
            )
            db.session.add(l)

        # Replace hazards
        for h in room.hazards:
            db.session.delete(h)
        haz_names = request.form.getlist('hazard_name')
        haz_descs = request.form.getlist('hazard_desc')
        haz_dcs = request.form.getlist('hazard_dc')
        haz_cons = request.form.getlist('hazard_consequence')
        for i, name in enumerate(haz_names):
            if not name.strip():
                continue
            h = RoomHazard(
                room_id=room.id,
                name=name.strip(),
                description=haz_descs[i] if i < len(haz_descs) else '',
                dc_or_target=haz_dcs[i] if i < len(haz_dcs) else '',
                consequence=haz_cons[i] if i < len(haz_cons) else '',
            )
            db.session.add(h)

        # Optional campaign Location link
        loc_id = request.form.get('location_id', '').strip()
        room.location_id = int(loc_id) if loc_id else None

        db.session.commit()
        flash(f'Location "{room.title}" saved.', 'success')
        return redirect(url_for('adventures.detail', adventure_id=adventure.id) + f'#room-{room.id}')

    all_locations = Location.query.filter_by(campaign_id=adventure.campaign_id).order_by(Location.name).all()
    return render_template('adventures/edit_room.html',
                           room=room,
                           adventure=adventure,
                           campaign=campaign,
                           all_locations=all_locations)


# ---------------------------------------------------------------------------
# Add room to a scene (POST)
# ---------------------------------------------------------------------------

@adventures_bp.route('/scenes/<int:scene_id>/add-room', methods=['POST'])
@login_required
def add_room(scene_id):
    scene = AdventureScene.query.get_or_404(scene_id)
    adventure = scene.act.adventure
    next_order = len(scene.rooms)
    # Auto-key: scene index A=0, B=1... + room number
    scene_letter = chr(65 + (scene.sort_order % 26))
    key = f'{scene_letter}{next_order + 1}'
    room = AdventureRoom(
        scene_id=scene.id,
        key=key,
        title='New Room',
        read_aloud='',
        gm_notes='',
        sort_order=next_order,
    )
    db.session.add(room)
    db.session.commit()
    return redirect(url_for('adventures.edit_room', room_id=room.id))


# ---------------------------------------------------------------------------
# Delete room
# ---------------------------------------------------------------------------

@adventures_bp.route('/rooms/<int:room_id>/delete', methods=['POST'])
@login_required
def delete_room(room_id):
    room = AdventureRoom.query.get_or_404(room_id)
    adventure = room.scene.act.adventure
    title = room.title
    db.session.delete(room)
    db.session.commit()
    flash(f'Room "{title}" deleted.', 'success')
    return redirect(url_for('adventures.detail', adventure_id=adventure.id))


# ---------------------------------------------------------------------------
# Room reveal toggle (AJAX — Adventure Runner)
# ---------------------------------------------------------------------------

@adventures_bp.route('/rooms/<int:room_id>/reveal', methods=['POST'])
@login_required
def toggle_reveal(room_id):
    """Toggle the revealed state of a room's read-aloud text.
    State persists in the DB so players see it immediately and it survives page refreshes.
    """
    room = AdventureRoom.query.get_or_404(room_id)
    room.is_revealed = not room.is_revealed
    db.session.commit()
    return jsonify({'revealed': room.is_revealed})


# ---------------------------------------------------------------------------
# Room card (AJAX — Adventure Runner loads this fragment)
# ---------------------------------------------------------------------------

@adventures_bp.route('/rooms/<int:room_id>/card')
@login_required
def room_card(room_id):
    """Return the room card HTML fragment for AJAX loading in the runner."""
    room = AdventureRoom.query.get_or_404(room_id)
    adventure = room.scene.act.adventure
    is_revealed = room.is_revealed

    # Build prev/next room for navigation
    all_rooms = []
    for act in adventure.acts:
        for sc in act.scenes:
            all_rooms.extend(sc.rooms)
    try:
        idx = next(i for i, r in enumerate(all_rooms) if r.id == room_id)
        prev_room = all_rooms[idx - 1] if idx > 0 else None
        next_room = all_rooms[idx + 1] if idx < len(all_rooms) - 1 else None
    except StopIteration:
        prev_room = next_room = None

    # Pass active session and existing log entry for Phase 20d session logging
    active_session_id = session.get(f'adventure_{adventure.id}_session_id')
    active_game_session = GameSession.query.get(active_session_id) if active_session_id else None
    existing_log = None
    if active_game_session:
        existing_log = AdventureRoomLog.query.filter_by(
            session_id=active_game_session.id, room_id=room_id).first()

    campaign_pcs = PlayerCharacter.query.filter_by(
        campaign_id=adventure.campaign_id, status='active'
    ).order_by(PlayerCharacter.character_name).all()

    return render_template('adventures/_room_card.html',
                           room=room,
                           adventure=adventure,
                           is_revealed=is_revealed,
                           prev_room=prev_room,
                           next_room=next_room,
                           active_game_session=active_game_session,
                           existing_log=existing_log,
                           campaign_pcs=campaign_pcs)


# ---------------------------------------------------------------------------
# Give room loot to a PC (creates a campaign Item record)
# ---------------------------------------------------------------------------

@adventures_bp.route('/loot/<int:loot_id>/give-to-pc', methods=['POST'])
@login_required
def give_loot_to_pc(loot_id):
    loot = RoomLoot.query.get_or_404(loot_id)
    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign'}), 400
    pc_id = request.json.get('pc_id') if request.is_json else request.form.get('pc_id')
    if not pc_id:
        return jsonify({'error': 'No PC specified'}), 400
    pc = PlayerCharacter.query.get_or_404(int(pc_id))
    if pc.campaign_id != campaign.id:
        return jsonify({'error': 'PC not in active campaign'}), 403

    item = Item(
        campaign_id=campaign.id,
        name=loot.name,
        description=loot.description or '',
        owner_pc_id=pc.id,
        is_player_visible=True,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item_id': item.id, 'pc_name': pc.character_name})


# ---------------------------------------------------------------------------
# Adventure Runner (at-table view)
# ---------------------------------------------------------------------------

@adventures_bp.route('/<int:adventure_id>/run')
@login_required
def run(adventure_id):
    adventure = Adventure.query.get_or_404(adventure_id)
    campaign = _get_active_campaign()
    # Default to first room if none selected
    first_room = None
    if adventure.acts and adventure.acts[0].scenes and adventure.acts[0].scenes[0].rooms:
        first_room = adventure.acts[0].scenes[0].rooms[0]

    # Active session for this adventure (stored in Flask session)
    active_session_id = session.get(f'adventure_{adventure_id}_session_id')
    active_game_session = GameSession.query.get(active_session_id) if active_session_id else None

    # Existing session log for the first room (if active session)
    first_room_log = None
    if active_game_session and first_room:
        first_room_log = AdventureRoomLog.query.filter_by(
            session_id=active_game_session.id, room_id=first_room.id).first()

    # Right-panel context: NPCs, quests, locations linked to this adventure
    linked_npcs   = NPC.query.filter_by(adventure_id=adventure_id).order_by(NPC.name).all()
    linked_quests = Quest.query.filter_by(adventure_id=adventure_id).order_by(Quest.name).all()
    active_location = None
    if active_game_session and getattr(active_game_session, 'active_location_id', None):
        active_location = Location.query.get(active_game_session.active_location_id)
    all_locations = Location.query.filter_by(campaign_id=campaign.id).order_by(Location.name).all() if campaign else []

    # Random tables: built-in (campaign_id=NULL) + campaign-specific
    if campaign:
        all_tables = RandomTable.query.filter(
            db.or_(RandomTable.campaign_id == campaign.id, RandomTable.campaign_id == None)
        ).order_by(RandomTable.is_builtin.desc(), RandomTable.name).all()
    else:
        all_tables = []

    campaign_quests = adventure.campaign_quests

    # PCs for combat tab — active PCs with their stats serialized
    raw_pcs = PlayerCharacter.query.filter_by(campaign_id=campaign.id, status='active').order_by(
        PlayerCharacter.character_name).all() if campaign else []

    def _pc_stat(pc, *keywords):
        """Return the first stat value whose template field name contains any keyword (case-insensitive)."""
        for stat in pc.stats:
            fname = (stat.template_field.stat_name or '').lower()
            if any(k in fname for k in keywords):
                try:
                    return int(stat.stat_value)
                except (TypeError, ValueError):
                    pass
        return None

    system = adventure.system_hint or 'generic'
    campaign_pcs = []
    for pc in raw_pcs:
        if system == 'icrpg':
            hearts = _pc_stat(pc, 'heart') or 1
            hp = None
            ac = _pc_stat(pc, 'armor', 'defense') or 0
        else:
            hearts = None
            hp = _pc_stat(pc, 'hp', 'hit point', 'health', 'max hp') or 10
            ac = _pc_stat(pc, 'ac', 'armor class', 'defense') or 10
        campaign_pcs.append({
            'id': pc.id,
            'name': pc.character_name,
            'player': pc.player_name,
            'class_or_role': pc.class_or_role or '',
            'hearts': hearts,
            'hp': hp,
            'ac': ac,
        })

    return render_template('adventures/runner.html',
                           adventure=adventure,
                           campaign=campaign,
                           first_room=first_room,
                           active_game_session=active_game_session,
                           existing_log=first_room_log,
                           linked_npcs=linked_npcs,
                           linked_quests=linked_quests,
                           campaign_quests=campaign_quests,
                           active_location=active_location,
                           all_locations=all_locations,
                           all_tables=all_tables,
                           campaign_pcs=campaign_pcs)


# ---------------------------------------------------------------------------
# Scene CRUD
# ---------------------------------------------------------------------------

@adventures_bp.route('/acts/<int:act_id>/add-scene', methods=['POST'])
@login_required
def add_scene(act_id):
    act = AdventureAct.query.get_or_404(act_id)
    adventure = act.adventure
    title = request.form.get('title', '').strip() or 'New Scene'
    scene_type = request.form.get('scene_type', '').strip()
    description = request.form.get('description', '').strip()
    scene = AdventureScene(
        act_id=act.id,
        title=title,
        scene_type=scene_type,
        description=description,
        sort_order=len(act.scenes),
    )
    db.session.add(scene)
    db.session.commit()
    flash(f'Scene "{scene.title}" added.', 'success')
    return redirect(url_for('adventures.detail', adventure_id=adventure.id) + '#tab-structure')


@adventures_bp.route('/scenes/<int:scene_id>/edit', methods=['POST'])
@login_required
def edit_scene(scene_id):
    scene = AdventureScene.query.get_or_404(scene_id)
    adventure = scene.act.adventure
    scene.title = request.form.get('title', scene.title).strip()
    scene.scene_type = request.form.get('scene_type', scene.scene_type or '').strip()
    scene.description = request.form.get('description', scene.description or '').strip()
    db.session.commit()
    flash(f'Scene "{scene.title}" updated.', 'success')
    return redirect(url_for('adventures.detail', adventure_id=adventure.id) + '#tab-structure')


@adventures_bp.route('/scenes/<int:scene_id>/delete', methods=['POST'])
@login_required
def delete_scene(scene_id):
    scene = AdventureScene.query.get_or_404(scene_id)
    adventure = scene.act.adventure
    title = scene.title
    db.session.delete(scene)
    db.session.commit()
    flash(f'Scene "{title}" deleted.', 'success')
    return redirect(url_for('adventures.detail', adventure_id=adventure.id) + '#tab-structure')


# ---------------------------------------------------------------------------
# Act CRUD
# ---------------------------------------------------------------------------

@adventures_bp.route('/<int:adventure_id>/add-act', methods=['POST'])
@login_required
def add_act(adventure_id):
    adventure = Adventure.query.get_or_404(adventure_id)
    next_number = len(adventure.acts) + 1
    title = request.form.get('title', '').strip() or f'Act {next_number}'
    act = AdventureAct(
        adventure_id=adventure.id,
        number=next_number,
        title=title,
        sort_order=next_number - 1,
    )
    db.session.add(act)
    db.session.commit()
    flash(f'Act "{act.title}" added.', 'success')
    return redirect(url_for('adventures.detail', adventure_id=adventure.id) + '#tab-structure')


@adventures_bp.route('/acts/<int:act_id>/edit', methods=['POST'])
@login_required
def edit_act(act_id):
    act = AdventureAct.query.get_or_404(act_id)
    adventure = act.adventure
    act.title = request.form.get('title', act.title).strip()
    act.description = request.form.get('description', act.description or '').strip()
    db.session.commit()
    flash(f'Act "{act.title}" updated.', 'success')
    return redirect(url_for('adventures.detail', adventure_id=adventure.id) + '#tab-structure')


@adventures_bp.route('/acts/<int:act_id>/delete', methods=['POST'])
@login_required
def delete_act(act_id):
    act = AdventureAct.query.get_or_404(act_id)
    adventure = act.adventure
    title = act.title
    db.session.delete(act)
    db.session.commit()
    flash(f'Act "{title}" deleted (all its scenes and rooms removed).', 'success')
    return redirect(url_for('adventures.detail', adventure_id=adventure.id) + '#tab-structure')


# ---------------------------------------------------------------------------
# Planning notes AJAX save
# ---------------------------------------------------------------------------

@adventures_bp.route('/<int:adventure_id>/planning-notes', methods=['POST'])
@login_required
def save_planning_notes(adventure_id):
    adventure = Adventure.query.get_or_404(adventure_id)
    adventure.planning_notes = request.form.get('planning_notes', '').strip()
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Entity linking (link/unlink NPC, Location, Quest, Item to adventure)
# ---------------------------------------------------------------------------

@adventures_bp.route('/<int:adventure_id>/link-entity', methods=['POST'])
@login_required
def link_entity(adventure_id):
    """Link an existing NPC/Location/Quest/Item to this adventure.
    entity_type='campaign_quest' links via adventure_quest_link M-to-M (campaign-spanning quests).
    All other types set entity.adventure_id directly.
    """
    adventure = Adventure.query.get_or_404(adventure_id)
    entity_type = request.form.get('entity_type')
    entity_id = request.form.get('entity_id', type=int)

    if entity_type == 'campaign_quest' and entity_id:
        quest = Quest.query.get(entity_id)
        if quest and quest not in adventure.campaign_quests:
            adventure.campaign_quests.append(quest)
            db.session.commit()
    else:
        model_map = {'npc': NPC, 'location': Location, 'quest': Quest, 'item': Item}
        model = model_map.get(entity_type)
        if model and entity_id:
            entity = model.query.get(entity_id)
            if entity:
                entity.adventure_id = adventure_id
                db.session.commit()
    return redirect(url_for('adventures.detail', adventure_id=adventure_id) + '#tab-entities')


@adventures_bp.route('/<int:adventure_id>/unlink-entity', methods=['POST'])
@login_required
def unlink_entity(adventure_id):
    """Unlink an NPC/Location/Quest/Item from this adventure."""
    adventure = Adventure.query.get_or_404(adventure_id)
    entity_type = request.form.get('entity_type')
    entity_id = request.form.get('entity_id', type=int)

    if entity_type == 'campaign_quest' and entity_id:
        quest = Quest.query.get(entity_id)
        if quest and quest in adventure.campaign_quests:
            adventure.campaign_quests.remove(quest)
            db.session.commit()
    else:
        model_map = {'npc': NPC, 'location': Location, 'quest': Quest, 'item': Item}
        model = model_map.get(entity_type)
        if model and entity_id:
            entity = model.query.get(entity_id)
            if entity and entity.adventure_id == adventure_id:
                entity.adventure_id = None
                db.session.commit()
    return redirect(url_for('adventures.detail', adventure_id=adventure_id) + '#tab-entities')


# ---------------------------------------------------------------------------
# Phase 20d: Session integration
# ---------------------------------------------------------------------------

@adventures_bp.route('/<int:adventure_id>/start-session', methods=['POST'])
@login_required
def start_session(adventure_id):
    """Create a new Session linked to this adventure and store in Flask session."""
    adventure = Adventure.query.get_or_404(adventure_id)
    campaign = _get_active_campaign()
    if not campaign:
        return jsonify({'error': 'No active campaign'}), 400

    # Auto-increment session number within this campaign
    last = (GameSession.query
            .filter_by(campaign_id=campaign.id)
            .order_by(GameSession.number.desc())
            .first())
    next_number = (last.number or 0) + 1 if last else 1

    game_session = GameSession(
        campaign_id=campaign.id,
        adventure_id=adventure_id,
        number=next_number,
        title=f'{adventure.name} — Session {next_number}',
        date_played=date.today(),
    )
    db.session.add(game_session)
    db.session.commit()

    # Store in Flask session so runner knows which session is active
    session[f'adventure_{adventure_id}_session_id'] = game_session.id

    return jsonify({
        'success': True,
        'session_id': game_session.id,
        'session_number': next_number,
        'session_url': url_for('sessions.session_detail', session_id=game_session.id),
    })


@adventures_bp.route('/rooms/<int:room_id>/log', methods=['POST'])
@login_required
def log_room(room_id):
    """Create or update an AdventureRoomLog entry for the active session."""
    room = AdventureRoom.query.get_or_404(room_id)
    adventure = room.scene.act.adventure
    session_id = session.get(f'adventure_{adventure.id}_session_id')
    if not session_id:
        return jsonify({'error': 'No active session'}), 400

    gm_notes = request.form.get('gm_notes', '').strip()
    creatures_defeated = request.form.get('creatures_defeated') == '1'
    loot_taken = request.form.get('loot_taken') == '1'

    # Upsert: one log per room per session
    log = AdventureRoomLog.query.filter_by(
        session_id=session_id, room_id=room_id).first()
    if log:
        log.gm_notes = gm_notes
        log.creatures_defeated = creatures_defeated
        log.loot_taken = loot_taken
    else:
        log = AdventureRoomLog(
            session_id=session_id,
            room_id=room_id,
            gm_notes=gm_notes,
            creatures_defeated=creatures_defeated,
            loot_taken=loot_taken,
        )
        db.session.add(log)

    db.session.commit()
    return jsonify({'success': True})


@adventures_bp.route('/rooms/<int:room_id>/clear', methods=['POST'])
@login_required
def toggle_clear(room_id):
    """Toggle is_cleared on a room (persistent in DB)."""
    room = AdventureRoom.query.get_or_404(room_id)
    room.is_cleared = not room.is_cleared
    if not room.is_cleared:
        room.cleared_notes = None
    db.session.commit()
    return jsonify({'cleared': room.is_cleared})


@adventures_bp.route('/<int:adventure_id>/generate-entities', methods=['POST'])
@login_required
def generate_entities(adventure_id):
    """Promote room creatures → NPCs and room loot → Items, all linked to
    this adventure. Idempotent: skips names that already exist in this adventure.

    Returns JSON: { success, npcs_created, items_created }
    """
    try:
        adventure = Adventure.query.get_or_404(adventure_id)
        from app.models import Campaign
        campaign = Campaign.query.get(adventure.campaign_id)
        if campaign is None:
            return jsonify({'error': 'Adventure has no campaign attached.'}), 400

        # Collect all rooms across all acts/scenes
        all_rooms = []
        for act in adventure.acts:
            for scene in act.scenes:
                all_rooms.extend(scene.rooms)

        # Existing NPC and Item names already linked to this adventure (for dedup)
        existing_npc_names = {n.name.lower() for n in NPC.query.filter_by(
            campaign_id=campaign.id, adventure_id=adventure.id).all()}
        existing_item_names = {i.name.lower() for i in Item.query.filter_by(
            campaign_id=campaign.id, adventure_id=adventure.id).all()}

        npcs_created = 0
        items_created = 0

        for room in all_rooms:
            # Creatures → NPCs
            for creature in room.creatures:
                if creature.name.lower() in existing_npc_names:
                    continue
                npc = NPC(
                    campaign_id=campaign.id,
                    name=creature.name,
                    role='Creature',
                    notes=creature.special_move or creature.actions or '',
                    adventure_id=adventure.id,
                )
                db.session.add(npc)
                db.session.flush()
                # Link to room as RoomNPC only if not already linked
                already_linked = any(rn.npc_id == npc.id for rn in room.room_npcs)
                if not already_linked:
                    db.session.add(RoomNPC(room_id=room.id, npc_id=npc.id))
                existing_npc_names.add(creature.name.lower())
                npcs_created += 1

            # Loot → Items
            for loot in room.loot:
                if loot.name.lower() in existing_item_names:
                    continue
                item = Item(
                    campaign_id=campaign.id,
                    name=loot.name,
                    type='loot',
                    description=loot.description or '',
                    adventure_id=adventure.id,
                )
                db.session.add(item)
                existing_item_names.add(loot.name.lower())
                items_created += 1

        db.session.commit()
        return jsonify({'success': True, 'npcs_created': npcs_created, 'items_created': items_created})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Runner in-panel helpers (quick note + location for at-table right panel)
# ---------------------------------------------------------------------------

@adventures_bp.route('/<int:adventure_id>/runner-note', methods=['POST'])
@login_required
def runner_note(adventure_id):
    """Add a timestamped quick note to the adventure's active session."""
    from datetime import datetime as _dt
    data = request.get_json(silent=True) or {}
    note_text = (data.get('note') or '').strip()
    if not note_text:
        return jsonify({'error': 'Note is empty.'}), 400

    active_session_id = session.get(f'adventure_{adventure_id}_session_id')
    if not active_session_id:
        return jsonify({'error': 'No active session for this adventure.'}), 400

    game_session = GameSession.query.get(active_session_id)
    if not game_session:
        return jsonify({'error': 'Session not found.'}), 404

    timestamp = _dt.utcnow().strftime('%H:%M')
    new_line = f'**[{timestamp}]** {note_text}'
    game_session.gm_notes = (game_session.gm_notes + '\n\n' + new_line) if game_session.gm_notes else new_line
    db.session.commit()
    return jsonify({'success': True})


@adventures_bp.route('/<int:adventure_id>/runner-location', methods=['POST'])
@login_required
def runner_location(adventure_id):
    """Set the active location on the adventure's current game session."""
    data = request.get_json(silent=True) or {}
    loc_id = data.get('location_id')

    active_session_id = session.get(f'adventure_{adventure_id}_session_id')
    if not active_session_id:
        return jsonify({'error': 'No active session for this adventure.'}), 400

    game_session = GameSession.query.get(active_session_id)
    if not game_session:
        return jsonify({'error': 'Session not found.'}), 404

    game_session.active_location_id = int(loc_id) if loc_id else None
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Adventure AI endpoints (migrated from session_mode)
# ---------------------------------------------------------------------------

@adventures_bp.route('/ai/npc-chat', methods=['POST'])
@login_required
def ai_npc_chat():
    """NPC dialogue generator — takes npc_id + situation, returns in-character lines."""
    from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider
    from app.models import Campaign as _Campaign
    if not is_ai_enabled():
        return jsonify({'error': 'AI is not configured. Go to Settings to set up a provider.'}), 403
    campaign_id = session.get('active_campaign_id')
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400
    data = request.get_json(silent=True) or {}
    npc_id   = data.get('npc_id')
    situation = (data.get('situation') or '').strip()
    requested_provider = data.get('provider')
    if requested_provider not in ('ollama', 'anthropic', None):
        requested_provider = None
    if not npc_id or not situation:
        return jsonify({'error': 'NPC and situation are required.'}), 400
    npc = NPC.query.filter_by(id=npc_id, campaign_id=campaign_id).first()
    if not npc:
        return jsonify({'error': 'NPC not found in this campaign.'}), 404
    campaign = _Campaign.query.get(campaign_id)
    active_session_id = session.get('current_session_id')
    game_session = GameSession.query.get(active_session_id) if active_session_id else None
    parts = [f'You are roleplaying as {npc.name}']
    if npc.role:
        parts[0] += f', a {npc.role}'
    parts[0] += ' in a tabletop RPG.'
    if npc.personality:
        parts.append(f'Personality: {npc.personality}')
    if npc.physical_description:
        parts.append(f'Physical appearance: {npc.physical_description}')
    if npc.faction_rel:
        faction_info = npc.faction_rel.name
        if npc.faction_rel.disposition:
            faction_info += f' ({npc.faction_rel.disposition})'
        parts.append(f'Faction: {faction_info}')
    if npc.secrets:
        parts.append(f'Secrets you know (use subtly, do not reveal directly): {npc.secrets}')
    if npc.notes:
        parts.append(f'Additional background: {npc.notes}')
    if game_session and getattr(game_session, 'active_location', None):
        parts.append(f'Current location: {game_session.active_location.name}')
    if campaign and campaign.ai_world_context:
        parts.append(f'World context: {campaign.ai_world_context}')
    parts.append(
        '\nWhen the GM describes a situation, respond with 3-4 short lines of dialogue '
        'that this character would say. Stay in character. Be concise — this is for '
        'quick reference at the game table, not prose. Include mannerisms or speech '
        'patterns that fit the personality. Each line should be a separate thing the '
        'NPC might say, giving the GM options to choose from.'
    )
    system_prompt = '\n\n'.join(parts)
    messages = [{'role': 'user', 'content': situation}]
    try:
        effective_provider = requested_provider or get_feature_provider('npc_chat')
        response = ai_chat(system_prompt, messages, max_tokens=512, provider=effective_provider)
        return jsonify({'response': response})
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 502


@adventures_bp.route('/ai/hazard-flavor', methods=['POST'])
@login_required
def ai_hazard_flavor():
    """Generate vivid sensory flavor text for a hazard."""
    from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider
    from app.models import Campaign as _Campaign
    if not is_ai_enabled():
        return jsonify({'error': 'AI is not configured. Check Settings.'}), 403
    campaign_id = session.get('active_campaign_id')
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400
    data = request.get_json(silent=True) or {}
    hazard = (data.get('hazard') or '').strip()
    if not hazard:
        return jsonify({'error': 'Describe the hazard first.'}), 400
    campaign = _Campaign.query.get(campaign_id)
    parts = [
        'You are a tabletop RPG narrator. Write vivid, sensory flavor text for a GM to read '
        'aloud when a hazard occurs at the table. '
        'Focus on what the players see, hear, smell, and feel. '
        'Keep it to 2-3 sentences — punchy and atmospheric, not a wall of text.'
    ]
    if campaign and campaign.ai_world_context:
        parts.append(f'World context: {campaign.ai_world_context}')
    system_prompt = '\n\n'.join(parts)
    messages = [{'role': 'user', 'content': f'Write flavor text for this hazard: {hazard}'}]
    try:
        response = ai_chat(system_prompt, messages, max_tokens=256,
                           provider=get_feature_provider('generate'))
        return jsonify({'flavor': response})
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 502


@adventures_bp.route('/ai/suggest-consequences', methods=['POST'])
@login_required
def ai_suggest_consequences():
    """Suggest narrative ripple effects based on what happened this session."""
    from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider
    from app.models import Campaign as _Campaign
    if not is_ai_enabled():
        return jsonify({'error': 'AI is not configured. Check Settings.'}), 403
    campaign_id = session.get('active_campaign_id')
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id required.'}), 400
    game_session = GameSession.query.filter_by(id=session_id, campaign_id=campaign_id).first()
    if not game_session:
        return jsonify({'error': 'Session not found.'}), 404
    campaign = _Campaign.query.get(campaign_id)
    context_parts = []
    if game_session.summary:
        context_parts.append(f'Session summary:\n{game_session.summary[:2000]}')
    if game_session.gm_notes:
        context_parts.append(f'GM notes:\n{game_session.gm_notes[:1000]}')
    quest_lines = [f'- {q.name} (status: {q.status})' for q in game_session.quests_touched]
    if quest_lines:
        context_parts.append('Quest statuses:\n' + '\n'.join(quest_lines))
    npc_lines = [f'- {n.name} (status: {n.status})' for n in game_session.npcs_featured]
    if npc_lines:
        context_parts.append('NPC statuses:\n' + '\n'.join(npc_lines))
    if not context_parts:
        return jsonify({'error': 'Not enough session data to suggest consequences. Add a summary first.'}), 400
    system_prompt = (
        'You are a narrative consequence designer for tabletop RPGs. '
        'Based on what happened in the last session, suggest 3-5 ripple effects '
        'that could emerge in future sessions — new threats, changed relationships, '
        'opened opportunities, or lingering complications. '
        'Format as a Markdown bullet list. Each consequence should be 1-2 sentences. '
        'Be specific to the events described, not generic.'
    )
    if campaign and campaign.ai_world_context:
        system_prompt += f'\n\nWorld context: {campaign.ai_world_context}'
    user_content = '\n\n'.join(context_parts)
    messages = [{'role': 'user', 'content': user_content}]
    try:
        response = ai_chat(system_prompt, messages, max_tokens=512,
                           provider=get_feature_provider('generate'))
        return jsonify({'consequences': response})
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 502
