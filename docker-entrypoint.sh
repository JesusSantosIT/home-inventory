#!/bin/sh
set -e

# Apply database migrations before starting the app
python manage.py migrate --noinput

# Optional: auto-create a superuser when DJANGO_SUPERUSER_PASSWORD is set.
# The password comes from .env — never hardcode credentials.
if [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput \
        --username "${DJANGO_SUPERUSER_USERNAME:-admin}" \
        --email "${DJANGO_SUPERUSER_EMAIL:-admin@localhost}" \
        || echo "Superuser already exists or creation failed - continuing"
fi

exec "$@"
