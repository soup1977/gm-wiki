import os

class Config:
    # The secret key is used by Flask to sign session cookies — keep it secret in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # In Docker, DATABASE_URL env var points to the mounted volume path.
    # Locally, falls back to the instance/ folder next to this file.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'gm_wiki.db')

    # This disables a noisy tracking feature we don't need
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploaded image files are stored in app/static/uploads/
    # We store only the filename in the database, not the full path
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Claude API key for AI Smart Fill. Set ANTHROPIC_API_KEY in your environment
    # or docker-compose.yml. If not set, Smart Fill features are hidden.
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    AI_ENABLED = bool(os.environ.get('ANTHROPIC_API_KEY'))