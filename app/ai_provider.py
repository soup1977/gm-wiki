"""
app/ai_provider.py — Provider-agnostic AI abstraction layer

Supports two backends:
  - Ollama (local, free) — talks to the Ollama REST API
  - Anthropic (cloud, paid) — uses the official anthropic Python SDK

All settings are read from the AppSetting database table, not environment
variables. This means the AI provider can be changed from the browser
without restarting the app.

Public functions:
  is_ai_enabled()   — True if a provider is configured and ready
  get_ai_config()   — dict of current AI settings
  ai_chat(...)      — send a prompt and get a response string back
"""

import json
import requests


class AIProviderError(Exception):
    """Raised when an AI provider call fails."""
    pass


def _get_settings():
    """Read AI settings from the database. Returns a dict."""
    from app.models import AppSetting
    return AppSetting.get_all_dict()


def is_ai_enabled():
    """Check if any AI provider is configured and could work."""
    settings = _get_settings()
    provider = settings.get('ai_provider', 'none')
    if provider == 'ollama':
        return bool(settings.get('ollama_url'))
    elif provider == 'anthropic':
        return bool(settings.get('anthropic_api_key'))
    return False


def get_ai_config():
    """Return a dict of current AI settings for display."""
    settings = _get_settings()
    return {
        'provider': settings.get('ai_provider', 'none'),
        'ollama_url': settings.get('ollama_url', 'http://localhost:11434'),
        'ollama_model': settings.get('ollama_model', 'llama3.1'),
        'anthropic_api_key': settings.get('anthropic_api_key', ''),
        'sd_url': settings.get('sd_url', ''),
        'sd_model': settings.get('sd_model', ''),
        'sd_sampler': settings.get('sd_sampler', 'DPM++ SDE'),
        'sd_steps': settings.get('sd_steps', '4'),
        'sd_cfg_scale': settings.get('sd_cfg_scale', '2'),
        'sd_width': settings.get('sd_width', '768'),
        'sd_height': settings.get('sd_height', '1024'),
    }


def ai_chat(system_prompt, messages, max_tokens=1024):
    """Send a chat request to the configured AI provider.

    Args:
        system_prompt: The system instruction string.
        messages: List of dicts with 'role' and 'content' keys.
                  Usually just [{'role': 'user', 'content': '...'}].
        max_tokens: Maximum response length (used by Anthropic; Ollama ignores).

    Returns:
        The assistant's response as a plain string.

    Raises:
        AIProviderError: If no provider is configured or the call fails.
    """
    config = get_ai_config()
    provider = config['provider']

    if provider == 'ollama':
        return _call_ollama(config, system_prompt, messages)
    elif provider == 'anthropic':
        return _call_anthropic(config, system_prompt, messages, max_tokens)
    else:
        raise AIProviderError('No AI provider configured. Go to Settings to set one up.')


def _call_ollama(config, system_prompt, messages):
    """Call the Ollama REST API."""
    url = config['ollama_url'].rstrip('/')
    model = config['ollama_model'] or 'llama3.1'

    # Ollama expects messages in OpenAI format
    ollama_messages = [{'role': 'system', 'content': system_prompt}]
    for msg in messages:
        ollama_messages.append({'role': msg['role'], 'content': msg['content']})

    try:
        resp = requests.post(
            f'{url}/api/chat',
            json={
                'model': model,
                'messages': ollama_messages,
                'stream': False,
            },
            timeout=300,  # 5 min — first request loads model into VRAM, can be slow
        )
        # Check for model-not-found (Ollama returns 404 when model isn't pulled)
        if resp.status_code == 404:
            try:
                err_body = resp.json().get('error', '')
            except Exception:
                err_body = ''
            raise AIProviderError(
                f'Model "{model}" not found on Ollama server. '
                f'Pull it first: ollama pull {model}'
            )
        resp.raise_for_status()
        data = resp.json()
        return data.get('message', {}).get('content', '')
    except AIProviderError:
        raise  # Re-raise our own errors without wrapping
    except requests.ConnectionError:
        raise AIProviderError(
            f'Cannot connect to Ollama at {url}. '
            'Make sure the Ollama server is running.'
        )
    except requests.Timeout:
        raise AIProviderError('Ollama request timed out. The model may be loading or the server is slow.')
    except requests.HTTPError as e:
        raise AIProviderError(f'Ollama returned an error: {e}')
    except (KeyError, json.JSONDecodeError) as e:
        raise AIProviderError(f'Unexpected response from Ollama: {e}')


def _call_anthropic(config, system_prompt, messages, max_tokens):
    """Call the Anthropic Claude API."""
    api_key = config['anthropic_api_key']
    if not api_key:
        raise AIProviderError('Anthropic API key is not set. Go to Settings to add it.')

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text.strip()
    except ImportError:
        raise AIProviderError('The anthropic Python package is not installed.')
    except Exception as e:
        error_msg = str(e)
        if 'authentication' in error_msg.lower() or 'api_key' in error_msg.lower():
            raise AIProviderError('Invalid Anthropic API key. Check your key in Settings.')
        raise AIProviderError(f'Anthropic API error: {error_msg}')
