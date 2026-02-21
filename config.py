import os

class Config:
    # The secret key is used by Flask to sign session cookies — keep it secret in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # This tells SQLAlchemy where to find (or create) the database file
    # 'instance' folder is Flask's conventional spot for local data files
    SQLALCHEMY_DATABASE_URI = 'sqlite:///gm_wiki.db'
    
    # This disables a noisy tracking feature we don't need
    SQLALCHEMY_TRACK_MODIFICATIONS = False