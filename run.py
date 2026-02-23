from dotenv import load_dotenv
load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    # debug=True means Flask will auto-reload when you save a file
    # and show detailed error pages — turn this off in production
    app.run(debug=True, host='0.0.0.0', port=5001)