#!/bin/sh
set -e

# Apply database migrations before starting the app
python manage.py migrate --noinput

exec "$@"
