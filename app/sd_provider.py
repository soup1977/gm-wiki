"""
app/sd_provider.py — Stable Diffusion (AUTOMATIC1111) image generation

Talks to the AUTOMATIC1111 WebUI API to generate images from text prompts.
The SD server URL is stored in the AppSetting database table and configured
from the Settings page.

Public functions:
  is_sd_enabled()  — True if sd_url is configured
  sd_generate(...)  — generate an image and save it to the uploads folder
"""

import base64
import os
import uuid

import requests


class SDProviderError(Exception):
    """Raised when a Stable Diffusion API call fails."""
    pass


def _get_sd_url():
    """Read the SD URL from database settings."""
    from app.models import AppSetting
    return (AppSetting.get('sd_url', '') or '').strip()


def _get_sd_model():
    """Read the selected SD model from database settings."""
    from app.models import AppSetting
    return (AppSetting.get('sd_model', '') or '').strip()


def is_sd_enabled():
    """Check if Stable Diffusion is configured."""
    return bool(_get_sd_url())


def _get_sd_settings():
    """Read SD generation settings from database, with sensible defaults."""
    from app.models import AppSetting
    return {
        'steps': int(AppSetting.get('sd_steps', '4')),
        'cfg_scale': float(AppSetting.get('sd_cfg_scale', '2')),
        'sampler_name': AppSetting.get('sd_sampler', 'DPM++ SDE Karras'),
        'width': int(AppSetting.get('sd_width', '768')),
        'height': int(AppSetting.get('sd_height', '1024')),
    }


def sd_generate(prompt, negative_prompt='', width=None, height=None):
    """Generate an image via AUTOMATIC1111 txt2img API.

    Args:
        prompt: The text prompt describing the image to generate.
        negative_prompt: What to exclude from the image.
        width: Image width in pixels (overrides saved setting if provided).
        height: Image height in pixels (overrides saved setting if provided).

    Returns:
        The saved filename (e.g. 'a1b2c3d4.png') in the uploads folder.

    Raises:
        SDProviderError: If SD is not configured or the API call fails.
    """
    url = _get_sd_url()
    if not url:
        raise SDProviderError('Stable Diffusion URL is not configured. Go to Settings to set it up.')

    url = url.rstrip('/')
    settings = _get_sd_settings()

    # Default negative prompt if none provided
    if not negative_prompt:
        negative_prompt = 'blurry, low quality, deformed, text, watermark, signature, extra limbs'

    payload = {
        'prompt': prompt,
        'negative_prompt': negative_prompt,
        'steps': settings['steps'],
        'width': width or settings['width'],
        'height': height or settings['height'],
        'cfg_scale': settings['cfg_scale'],
        'sampler_name': settings['sampler_name'],
        'seed': -1,
    }

    # Use the selected model if one is configured
    sd_model = _get_sd_model()
    if sd_model:
        payload['override_settings'] = {'sd_model_checkpoint': sd_model}

    try:
        resp = requests.post(
            f'{url}/sdapi/v1/txt2img',
            json=payload,
            timeout=120,
        )
        if resp.status_code != 200:
            # Try to extract the actual error detail from the JSON response
            try:
                err = resp.json()
                detail = err.get('detail') or err.get('error') or err.get('errors') or ''
                raise SDProviderError(f'Stable Diffusion error: {detail}')
            except (ValueError, KeyError):
                resp.raise_for_status()
        data = resp.json()
    except SDProviderError:
        raise
    except requests.ConnectionError:
        raise SDProviderError(
            f'Cannot connect to Stable Diffusion at {url}. '
            'Make sure AUTOMATIC1111 is running with --api flag.'
        )
    except requests.Timeout:
        raise SDProviderError('Image generation timed out. Try again or use a simpler prompt.')
    except requests.HTTPError as e:
        raise SDProviderError(f'Stable Diffusion returned an error: {e}')
    except Exception as e:
        raise SDProviderError(f'Unexpected error: {e}')

    # Extract the first image from the response
    images = data.get('images', [])
    if not images:
        raise SDProviderError('Stable Diffusion returned no images.')

    # Decode base64 image and save to uploads folder
    image_data = base64.b64decode(images[0])
    filename = f'{uuid.uuid4().hex}.png'

    from flask import current_app
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, 'wb') as f:
        f.write(image_data)

    return filename
