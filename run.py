from dotenv import load_dotenv
load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    # debug=True enables auto-reload when files change and detailed error pages.
    # In production (Docker), gunicorn is used instead of this script.
    import os
    debug = os.environ.get('FLASK_ENV', 'development') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=5001)