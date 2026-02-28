import requests as http_requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import db
from app.models import (Campaign, NPC, Location, Quest, Item, Session,
                        BestiaryEntry, CompendiumEntry, AppSetting)
from app.ai_provider import get_ai_config, ai_chat, AIProviderError
from app.routes.admin import admin_required

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def index():
    if request.method == 'POST':
        # Save settings from form
        AppSetting.set('ai_provider', request.form.get('ai_provider', 'none'))
        AppSetting.set('ollama_url', request.form.get('ollama_url', 'http://localhost:11434').strip())
        AppSetting.set('ollama_model', request.form.get('ollama_model', 'llama3.1').strip())
        AppSetting.set('anthropic_api_key', request.form.get('anthropic_api_key', '').strip())
        AppSetting.set('sd_url', request.form.get('sd_url', '').strip())
        AppSetting.set('sd_model', request.form.get('sd_model', '').strip())
        AppSetting.set('sd_sampler', request.form.get('sd_sampler', 'DPM++ SDE').strip())
        AppSetting.set('sd_steps', request.form.get('sd_steps', '4').strip())
        AppSetting.set('sd_cfg_scale', request.form.get('sd_cfg_scale', '2').strip())
        AppSetting.set('sd_width', request.form.get('sd_width', '768').strip())
        AppSetting.set('sd_height', request.form.get('sd_height', '1024').strip())
        # User registration toggle
        AppSetting.set('allow_signup', 'true' if request.form.get('allow_signup') else 'false')
        flash('Settings saved.', 'success')
        return redirect(url_for('settings.index'))

    config = get_ai_config()

    stats = {
        'campaigns': Campaign.query.count(),
        'npcs': NPC.query.count(),
        'locations': Location.query.count(),
        'quests': Quest.query.count(),
        'sessions': Session.query.count(),
        'item_count': Item.query.count(),
        'bestiary': BestiaryEntry.query.count(),
        'compendium': CompendiumEntry.query.count(),
    }

    allow_signup = AppSetting.get('allow_signup', 'true') == 'true'

    return render_template('settings/index.html', ai_config=config, stats=stats,
                           allow_signup=allow_signup)


@settings_bp.route('/test-ollama')
@login_required
@admin_required
def test_ollama():
    """AJAX endpoint: test Ollama connection with a simple prompt."""
    try:
        result = ai_chat(
            system_prompt='Reply with exactly: OK',
            messages=[{'role': 'user', 'content': 'Say OK'}],
            max_tokens=10,
        )
        return jsonify({'ok': True, 'message': f'Connected to Ollama. Response: {result[:50]}'})
    except AIProviderError as e:
        return jsonify({'ok': False, 'message': str(e)})


@settings_bp.route('/test-anthropic')
@login_required
@admin_required
def test_anthropic():
    """AJAX endpoint: test Anthropic API key."""
    config = get_ai_config()
    if not config.get('anthropic_api_key'):
        return jsonify({'ok': False, 'message': 'No API key entered.'})
    try:
        # Temporarily force anthropic provider for the test
        result = ai_chat(
            system_prompt='Reply with exactly: OK',
            messages=[{'role': 'user', 'content': 'Say OK'}],
            max_tokens=10,
        )
        return jsonify({'ok': True, 'message': f'Connected to Anthropic. Response: {result[:50]}'})
    except AIProviderError as e:
        return jsonify({'ok': False, 'message': str(e)})


@settings_bp.route('/test-sd')
@login_required
@admin_required
def test_sd():
    """AJAX endpoint: test Stable Diffusion connection."""
    config = get_ai_config()
    sd_url = (config.get('sd_url') or '').strip()
    if not sd_url:
        return jsonify({'ok': False, 'message': 'No Stable Diffusion URL configured.'})
    try:
        resp = http_requests.get(f'{sd_url.rstrip("/")}/sdapi/v1/sd-models', timeout=10)
        resp.raise_for_status()
        models = resp.json()
        model_names = [m.get('model_name', m.get('title', '?')) for m in models[:3]]
        return jsonify({
            'ok': True,
            'message': f'Connected. {len(models)} model(s) available: {", ".join(model_names)}'
        })
    except http_requests.ConnectionError:
        return jsonify({'ok': False, 'message': f'Cannot connect to {sd_url}. Is AUTOMATIC1111 running with --api?'})
    except Exception as e:
        return jsonify({'ok': False, 'message': f'Error: {e}'})


@settings_bp.route('/sd-models')
@login_required
@admin_required
def sd_models():
    """AJAX endpoint: fetch available SD models for the dropdown."""
    config = get_ai_config()
    sd_url = (config.get('sd_url') or '').strip()
    if not sd_url:
        return jsonify({'ok': False, 'models': [], 'message': 'No Stable Diffusion URL configured.'})
    try:
        resp = http_requests.get(f'{sd_url.rstrip("/")}/sdapi/v1/sd-models', timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        # Filter out models that won't work for txt2img generation
        skip = ('inpaint', 'edit', 'pix2pix', 'instruct')
        models = []
        for m in raw:
            name = (m.get('model_name') or m.get('title') or '').lower()
            if any(kw in name for kw in skip):
                continue
            models.append({'name': m.get('model_name', m.get('title', '?')),
                           'title': m.get('title', '?')})
        return jsonify({'ok': True, 'models': models})
    except http_requests.ConnectionError:
        return jsonify({'ok': False, 'models': [], 'message': f'Cannot connect to {sd_url}.'})
    except Exception as e:
        return jsonify({'ok': False, 'models': [], 'message': f'Error: {e}'})
