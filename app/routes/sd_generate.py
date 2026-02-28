"""
app/routes/sd_generate.py — Stable Diffusion image generation API endpoint

POST /api/sd/generate
  JSON body: { "prompt": "...", "negative_prompt": "..." }
  Returns:   { "ok": true, "filename": "abc.png", "url": "/static/uploads/abc.png" }
"""

from flask import Blueprint, request, jsonify, url_for, session
from flask_login import login_required, current_user
from app.sd_provider import sd_generate, SDProviderError, is_sd_enabled
from app.models import Campaign

sd_generate_bp = Blueprint('sd_generate', __name__, url_prefix='/api/sd')


@sd_generate_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    if not is_sd_enabled():
        return jsonify({'ok': False, 'error': 'Stable Diffusion is not configured. Go to Settings.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'error': 'Request must be JSON.'}), 400

    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({'ok': False, 'error': 'No prompt provided.'}), 400

    # Prepend campaign-level style prompt if set
    campaign_id = session.get('active_campaign_id')
    if campaign_id:
        campaign = Campaign.query.filter_by(
            id=campaign_id, user_id=current_user.id
        ).first()
        if campaign and campaign.image_style_prompt:
            prompt = campaign.image_style_prompt.strip() + ', ' + prompt

    negative_prompt = data.get('negative_prompt', '').strip()

    try:
        filename = sd_generate(prompt, negative_prompt)
        img_url = url_for('static', filename='uploads/' + filename)
        return jsonify({'ok': True, 'filename': filename, 'url': img_url})
    except SDProviderError as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
