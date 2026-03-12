import requests as http_requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import db
from app.models import (Campaign, NPC, Location, Quest, Item, Session,
                        BestiaryEntry, CompendiumEntry, AppSetting)
from app.ai_provider import get_ai_config, get_available_providers, ai_chat, AIProviderError, FEATURE_KEYS
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
        AppSetting.set('anthropic_model', request.form.get('anthropic_model', 'claude-haiku-4-5-20251001'))
        AppSetting.set('grok_api_key', request.form.get('grok_api_key', '').strip())
        AppSetting.set('grok_model', request.form.get('grok_model', 'grok-3-mini'))
        AppSetting.set('sd_url', request.form.get('sd_url', '').strip())
        AppSetting.set('sd_model', request.form.get('sd_model', '').strip())
        AppSetting.set('sd_sampler', request.form.get('sd_sampler', 'DPM++ SDE').strip())
        AppSetting.set('sd_steps', request.form.get('sd_steps', '4').strip())
        AppSetting.set('sd_cfg_scale', request.form.get('sd_cfg_scale', '2').strip())
        AppSetting.set('sd_width', request.form.get('sd_width', '768').strip())
        AppSetting.set('sd_height', request.form.get('sd_height', '1024').strip())
        AppSetting.set('sd_negative_prompt', request.form.get('sd_negative_prompt', '').strip())
        # Per-feature AI provider overrides
        for key in FEATURE_KEYS:
            AppSetting.set(f'ai_feature_{key}',
                           request.form.get(f'ai_feature_{key}', 'default'))
        # User registration toggle
        AppSetting.set('allow_signup', 'true' if request.form.get('allow_signup') else 'false')
        # Editable AI prompts (empty string means "use hardcoded default")
        for key in ('ai_prompt_smart_fill', 'ai_prompt_generate', 'ai_prompt_brainstorm_arcs',
                    'ai_prompt_session_prep', 'ai_prompt_generate_adventure',
                    'ai_prompt_flesh_out_room', 'ai_prompt_generate_scene_rooms',
                    'ai_prompt_generate_room_creatures', 'ai_prompt_generate_room_loot',
                    'ai_prompt_brainstorm_adventure', 'ai_prompt_npc_chat',
                    'ai_prompt_hazard_flavor', 'ai_prompt_suggest_consequences',
                    'ai_prompt_suggest_milestones', 'ai_prompt_import_table'):
            AppSetting.set(key, request.form.get(key, '').strip())
        # AI token limits
        AppSetting.set('ai_max_tokens_standard',
                       request.form.get('ai_max_tokens_standard', '2048').strip() or '2048')
        AppSetting.set('ai_max_tokens_generate',
                       request.form.get('ai_max_tokens_generate', '2048').strip() or '2048')
        AppSetting.set('ai_max_tokens_assistant',
                       request.form.get('ai_max_tokens_assistant', '4096').strip() or '4096')
        AppSetting.set('ai_max_tokens_adventure',
                       request.form.get('ai_max_tokens_adventure', '8192').strip() or '8192')
        # Activity log settings
        AppSetting.set('activity_log_retention_days',
                       request.form.get('activity_log_retention_days', '90').strip() or '90')
        AppSetting.set('activity_log_max_rows',
                       request.form.get('activity_log_max_rows', '10000').strip() or '10000')
        flash('Settings saved.', 'success')
        return redirect(url_for('settings.index'))

    config = get_ai_config()
    available_providers = get_available_providers()

    # Load per-feature provider settings
    feature_providers = {key: AppSetting.get(f'ai_feature_{key}', 'default')
                         for key in FEATURE_KEYS}

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

    # AI token limits
    ai_max_tokens_standard = AppSetting.get('ai_max_tokens_standard', '2048')
    ai_max_tokens_generate = AppSetting.get('ai_max_tokens_generate', '2048')
    ai_max_tokens_assistant = AppSetting.get('ai_max_tokens_assistant', '4096')
    ai_max_tokens_adventure = AppSetting.get('ai_max_tokens_adventure', '8192')

    # Activity log settings
    activity_log_retention_days = AppSetting.get('activity_log_retention_days', '90')
    activity_log_max_rows = AppSetting.get('activity_log_max_rows', '10000')

    # Load editable AI prompts — show stored override, or built-in default if none saved
    from app.routes.ai import DEFAULT_PROMPTS
    ai_prompts = {
        key: AppSetting.get(f'ai_prompt_{key}') or DEFAULT_PROMPTS[key]
        for key in ('smart_fill', 'generate', 'brainstorm_arcs',
                    'session_prep', 'generate_adventure',
                    'flesh_out_room', 'generate_scene_rooms',
                    'generate_room_creatures', 'generate_room_loot',
                    'brainstorm_adventure', 'npc_chat',
                    'hazard_flavor', 'suggest_consequences',
                    'suggest_milestones', 'import_table')
    }

    return render_template('settings/index.html', ai_config=config, stats=stats,
                           allow_signup=allow_signup,
                           available_providers=available_providers,
                           feature_providers=feature_providers,
                           ai_prompts=ai_prompts,
                           ai_max_tokens_standard=ai_max_tokens_standard,
                           ai_max_tokens_generate=ai_max_tokens_generate,
                           ai_max_tokens_assistant=ai_max_tokens_assistant,
                           ai_max_tokens_adventure=ai_max_tokens_adventure,
                           activity_log_retention_days=activity_log_retention_days,
                           activity_log_max_rows=activity_log_max_rows)


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


@settings_bp.route('/test-grok')
@login_required
@admin_required
def test_grok():
    """AJAX endpoint: test Grok (xAI) API key."""
    config = get_ai_config()
    if not config.get('grok_api_key'):
        return jsonify({'ok': False, 'message': 'No Grok API key entered.'})
    try:
        result = ai_chat(
            system_prompt='Reply with exactly: OK',
            messages=[{'role': 'user', 'content': 'Say OK'}],
            max_tokens=10,
            provider='grok',
        )
        return jsonify({'ok': True, 'message': f'Connected to Grok. Response: {result[:50]}'})
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
