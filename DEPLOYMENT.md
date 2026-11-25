# Production Deployment

## 1. Environment

Copy `.env.example` to `.env` and fill in real values:

```bash
SECRET_KEY=<generate: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
ALLOWED_HOSTS=your-domain.com
SITE_URL=https://your-domain.com
TRUST_PROXY=1            # if behind nginx/Caddy terminating TLS
```

## 2. Install & prepare

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py check --deploy
```

## 3. Run with Waitress (Windows/Linux, no compile needed)

```bash
waitress-serve --host=0.0.0.0 --port=8000 home_inventory.wsgi:application
```

Or via `manage.py`:
```bash
python manage.py runserver  # dev only - never use in production
```

For a Windows service, use NSSM or Task Scheduler to run the waitress command at startup.

## 4. Reverse proxy with TLS (required)

The external-household API **rejects non-HTTPS requests** when `DEBUG=False`,
so you must serve the app over HTTPS. Easiest options:

- **Caddy** (simplest — automatic HTTPS):
  ```
  your-domain.com {
      reverse_proxy localhost:8000
  }
  ```
- **nginx**: proxy_pass to `127.0.0.1:8000`, plus a certbot/Let's Encrypt cert.

With `TRUST_PROXY=1` set, Django correctly detects HTTPS through the proxy.

## 5. Database

SQLite (default) is fine for a single household. For heavier use, set
`DB_ENGINE=postgresql` + `DB_*` vars in `.env` and run migrations.

## 6. Backups

- SQLite: copy `db.sqlite3` + the `media/` folder
- Postgres: `pg_dump`
- Schedule daily; test restores.

## Notes

- QR codes embed `SITE_URL` — set it correctly or scans will point nowhere.
- After changing `SITE_URL`, regenerate item QR codes if needed.
- Rate limiting is IP-based; behind a proxy ensure `X-Forwarded-For` is set
  (Waitress passes it through; `TRUST_PROXY=1` handles the scheme).
