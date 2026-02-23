import os

class Config:
    # The secret key is used by Flask to sign session cookies — keep it secret in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # This tells SQLAlchemy where to find (or create) the database file
    # 'instance' folder is Flask's conventional spot for local data files
    SQLALCHEMY_DATABASE_URI = 'sqlite:///gm_wiki.db'

    # This disables a noisy tracking feature we don't need
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploaded image files are stored in app/static/uploads/
    # We store only the filename in the database, not the full path
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}