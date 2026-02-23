from flask import Blueprint, render_template, jsonify, current_app
from app.models import Campaign, NPC, Location, Quest, Item, Session, BestiaryEntry, CompendiumEntry

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('/')
def index():
    ai_enabled = current_app.config.get('AI_ENABLED', False)

    # Gather some app stats for the info panel
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

    return render_template('settings/index.html', ai_enabled=ai_enabled, stats=stats)


@settings_bp.route('/test-ai')
def test_ai():
    """AJAX endpoint: test whether the Claude API key is valid."""
    if not current_app.config.get('AI_ENABLED'):
        return jsonify({'ok': False, 'message': 'No API key configured.'})
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
        # Minimal API call — just check that auth works
        client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=10,
            messages=[{'role': 'user', 'content': 'Reply with the word OK only.'}],
        )
        return jsonify({'ok': True, 'message': 'Connected to Claude API successfully.'})
    except Exception as e:
        return jsonify({'ok': False, 'message': f'API error: {str(e)}'})
