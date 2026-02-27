from flask import Blueprint, jsonify, request, session
from app import db
from app.models import (Faction, Location, NPC, Quest, Item,
                        Session as GameSession, RandomTable, BestiaryEntry)

quick_create_bp = Blueprint('quick_create', __name__, url_prefix='/api')


def get_active_campaign_id():
    return session.get('active_campaign_id')


# Config for each entity type: model class, name field, campaign-scoped, defaults
ENTITY_CONFIG = {
    'faction': {
        'model': Faction,
        'name_field': 'name',
        'campaign_scoped': True,
        'defaults': {'disposition': 'unknown'},
    },
    'location': {
        'model': Location,
        'name_field': 'name',
        'campaign_scoped': True,
        'defaults': {},
    },
    'npc': {
        'model': NPC,
        'name_field': 'name',
        'campaign_scoped': True,
        'defaults': {'status': 'alive'},
    },
    'quest': {
        'model': Quest,
        'name_field': 'name',
        'campaign_scoped': True,
        'defaults': {'status': 'active'},
    },
    'item': {
        'model': Item,
        'name_field': 'name',
        'campaign_scoped': True,
        'defaults': {},
    },
    'session': {
        'model': GameSession,
        'name_field': 'title',
        'campaign_scoped': True,
        'defaults': {},
    },
    'random_table': {
        'model': RandomTable,
        'name_field': 'name',
        'campaign_scoped': True,
        'defaults': {},
    },
    'bestiary': {
        'model': BestiaryEntry,
        'name_field': 'name',
        'campaign_scoped': False,
        'defaults': {'stat_block': 'TBD'},
    },
}


@quick_create_bp.route('/quick-create/<entity_type>', methods=['POST'])
def quick_create(entity_type):
    config = ENTITY_CONFIG.get(entity_type)
    if not config:
        return jsonify({'error': f'Unknown entity type: {entity_type}'}), 400

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400

    model = config['model']
    name_field = config['name_field']
    campaign_scoped = config['campaign_scoped']

    campaign_id = get_active_campaign_id()
    if campaign_scoped and not campaign_id:
        return jsonify({'error': 'No active campaign selected.'}), 400

    # Check for duplicate by name within scope
    query = model.query.filter(getattr(model, name_field) == name)
    if campaign_scoped:
        query = query.filter_by(campaign_id=campaign_id)
    existing = query.first()

    if existing:
        return jsonify({'id': existing.id, 'name': getattr(existing, name_field)})

    # Build the new record
    kwargs = {name_field: name}
    kwargs.update(config['defaults'])
    if campaign_scoped:
        kwargs['campaign_id'] = campaign_id

    # Auto-assign next session number
    if entity_type == 'session':
        max_num = db.session.query(db.func.max(GameSession.number)).filter_by(
            campaign_id=campaign_id
        ).scalar() or 0
        kwargs['number'] = max_num + 1

    record = model(**kwargs)
    db.session.add(record)
    db.session.commit()

    return jsonify({'id': record.id, 'name': getattr(record, name_field)}), 201
