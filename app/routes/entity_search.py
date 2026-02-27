"""Unified entity search API for the shortcode autocomplete panel.

GET /api/entity-search?type=loc&q=Portland
Returns JSON array of matching entities (max 10), scoped to active campaign.
"""

from flask import Blueprint, jsonify, request, session
from app.shortcode import TYPE_CONFIG, _get_model

entity_search_bp = Blueprint('entity_search', __name__, url_prefix='/api')


@entity_search_bp.route('/entity-search')
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
