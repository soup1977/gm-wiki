#!/bin/bash
set -e

echo "Running database migrations..."
FLASK_APP=run.py python3 -m flask db upgrade

echo "Starting The War Table..."
exec gunicorn --bind 0.0.0.0:5001 --workers 2 run:app
