"""Unified entity search and preview API.

GET /api/entity-search?type=loc&q=Portland
Returns JSON array of matching entities (max 10), scoped to active campaign.

GET /api/entity-preview/<type>/<id>
Returns a lightweight JSON summary of a single entity for shortcode popovers.
"""

from flask import Blueprint, jsonify, request, session
from flask_login import login_required
from app.shortcode import TYPE_CONFIG, _get_model

entity_search_bp = Blueprint('entity_search', __name__, url_prefix='/api')


@entity_search_bp.route('/entity-search')
@login_required
def search():
    type_key = request.args.get('type', '').strip().lower()
    q = request.args.get('q', '').strip()
    campaign_id = session.get('active_campaign_id')

    if type_key not in TYPE_CONFIG:
        return jsonify([])

    if not campaign_id:
        return jsonify([])

    cfg = TYPE_CONFIG[type_key]
    try:
        model_cls = _get_model(cfg['model'])
    except AttributeError:
        return jsonify([])

    name_col = getattr(model_cls, cfg['name_field'])

    query = model_cls.query.filter(model_cls.campaign_id == campaign_id)
    if q:
        query = query.filter(name_col.ilike(f'%{q}%'))
    query = query.order_by(name_col).limit(10)

    results = []
    for entity in query.all():
        results.append({
            'id':   entity.id,
            'name': getattr(entity, cfg['name_field']),
            'type': type_key,
        })

    return jsonify(results)


@entity_search_bp.route('/entity-preview/<string:entity_type>/<int:entity_id>')
@login_required
def entity_preview(entity_type, entity_id):
    """Return a lightweight JSON summary of one entity for shortcode hover popovers."""
    if entity_type not in TYPE_CONFIG:
        return jsonify({'error': 'Unknown type'}), 404

    cfg = TYPE_CONFIG[entity_type]
    try:
        model_cls = _get_model(cfg['model'])
    except AttributeError:
        return jsonify({'error': 'Not found'}), 404

    entity = model_cls.query.get(entity_id)
    if not entity:
        return jsonify({'error': 'Not found'}), 404

    name = getattr(entity, cfg['name_field'], '')
    # Try common subtitle/description fields in order of preference
    subtitle = (getattr(entity, 'subtitle', None)
                or getattr(entity, 'role', None)
                or getattr(entity, 'type', None)
                or '')
    status = getattr(entity, 'status', None) or ''

    return jsonify({'name': name, 'subtitle': subtitle, 'status': status})
