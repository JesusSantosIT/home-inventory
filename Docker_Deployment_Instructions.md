# Docker Deployment Guide — Home Inventory

Deploys the app with **PostgreSQL** and **Waitress** behind Docker Compose.
Two containers: `app` (Django + WhiteNoise static files) and `db` (Postgres 16).

---

## Prerequisites

- **Docker Desktop** (Windows/Mac) or Docker Engine + Compose plugin (Linux)
- A domain name pointing at your server (for HTTPS — required for the lending API)
- ~1 GB free RAM, ~2 GB disk

Verify:
```bash
docker --version
docker compose version
```

---

## 1. Configure environment

Copy the example and fill in real values:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
SECRET_KEY=<generate one — see below>
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
SITE_URL=https://your-domain.com
TRUST_PROXY=1

# PostgreSQL (used by docker-compose automatically)
DB_ENGINE=postgresql
DB_NAME=inventory
DB_USER=inventory
DB_PASSWORD=<strong-random-password>
DB_HOST=db
DB_PORT=5432
```

Generate secrets:
```bash
# SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# DB_PASSWORD (or any random string)
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

> `.env` is excluded from the image via `.dockerignore` — secrets never get baked in.

---

## 2. Build and start

```bash
docker compose up -d --build
```

First start does, in order:
1. Postgres container starts, waits for `pg_isready` healthcheck
2. App image builds (pip install → collectstatic)
3. Entrypoint runs `python manage.py migrate` automatically
4. Waitress serves on port 8000

Check status:
```bash
docker compose ps
docker compose logs -f app      # follow app logs
docker compose logs -f db       # follow db logs
```

Verify it's up:
```bash
curl -I http://localhost:8000/    # expect 302 -> /login/
```

---

## 3. Create your admin user (required — no default credentials)

A fresh deployment has **no users and no default login**. Create the first
account before anything else can log in:

```bash
docker compose exec app python manage.py createsuperuser
```

Then set your profile role to **admin** (via Django admin at `/admin/` →
User Profiles, or the in-app "Manage Roles" page).

---

## 4. HTTPS (required)

The external-household API **rejects non-HTTPS requests** when `DEBUG=False`.
Put a TLS-terminating proxy in front.

### Option A — Caddy (recommended, automatic HTTPS)

Install Caddy, create `Caddyfile`:

```
your-domain.com {
    reverse_proxy localhost:8000
}
```

```bash
caddy run
```

Caddy gets and renews the Let's Encrypt cert automatically.

### Option B — nginx + Certbot

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

`TRUST_PROXY=1` in `.env` makes Django trust `X-Forwarded-Proto` so
`request.is_secure()` works correctly.

---

## 5. Persistent data

| Data | Storage | Backup |
|---|---|---|
| Inventory DB | `pgdata` volume | `docker compose exec db pg_dump -U inventory inventory > backup.sql` |
| Uploaded files (docs, images) | `media` volume | copy the volume or `docker run --rm -v home_inventory_media:/data -v ${PWD}:/backup alpine tar czf /backup/media.tar.gz -C /data .` |

List volumes: `docker volume ls | grep home_inventory`

---

## 6. Routine operations

```bash
# View logs
docker compose logs -f app

# Restart app
docker compose restart app

# After code changes: rebuild
docker compose up -d --build

# Run manage.py commands
docker compose exec app python manage.py <command>
# e.g. createsuperuser, changepassword, shell, collectstatic

# Stop everything
docker compose down          # keeps volumes/data
docker compose down -v       # WARNING: deletes DB + media volumes
```

---

## 7. Updates

```bash
git pull
docker compose up -d --build    # rebuilds app image, runs migrations on start
docker compose exec app python manage.py collectstatic --noinput   # if static changed
```

Migrations run automatically on container start via `docker-entrypoint.sh`.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `DB_PASSWORD` error on `up` | Set it in `.env` — compose refuses to start without it |
| App can't reach DB | `docker compose ps` — db must show "healthy"; check `docker compose logs db` |
| API returns "HTTPS required" | TLS not set up or `TRUST_PROXY` missing — see step 4 |
| Static files 404 | Rebuild: `docker compose up -d --build` (collectstatic runs at build) |
| QR codes point to localhost | Set `SITE_URL=https://your-domain.com` in `.env`, rebuild |
| Out of memory | Postgres default is fine for household scale; limit with `mem_limit` in compose if needed |
| Windows file-watch issues | Not applicable — production doesn't use runserver |

---

## Architecture notes

- **Waitress** serves Django (threads=8) — no compile step, works everywhere
- **WhiteNoise** serves static files from the app container (collected at build)
- **Media uploads** persist in the `media` Docker volume
- **Postgres** is only reachable inside the compose network — no host port exposed
- Rate limiting uses Django's local-memory cache — fine at household scale;
  for multi-instance deployments switch `CACHES` to Redis
