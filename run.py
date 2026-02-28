from dotenv import load_dotenv
load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    # debug=True means Flask will auto-reload when you save a file
    # and show detailed error pages. Only enabled for local development.
    import os
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=5001)