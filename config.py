import os

class Config:
    # The secret key is used by Flask to sign session cookies — keep it secret in production.
    # In production (Docker), SECRET_KEY must be set as an environment variable.
    # Locally, a dev-only fallback is used so you don't need a .env file just to run the app.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY and os.environ.get('FLASK_ENV') != 'development':
        import warnings
        warnings.warn('SECRET_KEY not set — using insecure default. Set SECRET_KEY env var in production!')
        SECRET_KEY = 'dev-secret-key-not-for-production'
    elif not SECRET_KEY:
        SECRET_KEY = 'dev-secret-key-not-for-production'

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

    # Session cookie security — protects against XSS and CSRF attacks
    SESSION_COOKIE_HTTPONLY = True       # JavaScript can't read the session cookie
    SESSION_COOKIE_SAMESITE = 'Lax'     # Cookie only sent for same-site requests
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'

    # Maximum upload size (16 MB) — prevents large file uploads from consuming memory
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # Claude API key for AI Smart Fill. Set ANTHROPIC_API_KEY in your environment
    # or docker-compose.yml. If not set, Smart Fill features are hidden.
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    AI_ENABLED = bool(os.environ.get('ANTHROPIC_API_KEY'))