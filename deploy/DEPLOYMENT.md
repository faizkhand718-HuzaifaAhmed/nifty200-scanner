# Deployment Guide — NIFTY 200 Opportunity Scanner

This is a step-by-step guide to deploying the backend and frontend to a
production (or staging) environment. Read the whole thing once before
starting, especially the "Live trading" section near the end — it applies
even if you have no intention of enabling live trading soon, because the
defaults matter from day one.

**Before you start:** everything in this guide was written and reviewed
carefully, but `fastapi`/`uvicorn`/`docker` were not installable/runnable in
the sandbox this was built in (no network access there). The backend's
core logic (indicators, scoring, risk management, brokers, etc.) has been
run and tested extensively; the deployment plumbing in this guide has
been syntax-checked and reasoned through, not run end-to-end. **Do a full
staging deployment and work through this guide for real before trusting
it in production.**

---

## 1. Prerequisites

- A Postgres 14+ instance (managed — RDS/Cloud SQL — or self-hosted)
- Python 3.12, Node.js 20 (if not using Docker)
- Docker + Docker Compose (recommended path) OR systemd (alternative path,
  see step 8)
- A domain name and TLS certificate (Let's Encrypt via certbot is fine)
- A secrets manager, or at minimum a secure way to inject environment
  variables at deploy time (see step 3 — do not skip this)

---

## 2. Get the code and set the version

```bash
git clone <your-repo-url> nifty200-scanner
cd nifty200-scanner
export APP_VERSION=$(git rev-parse --short HEAD)   # or a real semantic version tag
```

---

## 3. Environment variables and secret management

**Copy the template, do not commit the real file:**
```bash
cp backend/.env.example backend/.env
```

`backend/.env.example` documents every variable this application reads.
Fill in `backend/.env` with real values for your environment. `.env` is
already covered by `.gitignore` — verify this with `git status` before your
first commit; a leaked `.env` in git history is a real, hard-to-undo
incident.

**Never put a real secret in a file that gets committed, built into a
Docker image, or logged.** Concretely:
- `DATABASE_URL`, `SECRET_KEY`, and (if live trading is ever enabled) your
  broker's `*_API_KEY`/`*_API_SECRET`/`*_ACCESS_TOKEN` are read from
  environment variables only — see `backend/app/core/config.py` and
  `backend/app/brokers/models.py`'s `BrokerCredentials.from_env()`. There
  is no code path anywhere in this codebase that reads a secret from a
  source-controlled file.
- Generate `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`
  — never reuse a value from an example or a different environment.

**Recommended: use a real secrets manager in production**, not a `.env`
file on disk:
- **AWS**: store secrets in Secrets Manager, inject them into the ECS task
  definition / EC2 instance as environment variables at launch (ECS task
  definitions support this natively via `secrets:`).
- **GCP**: Secret Manager + Cloud Run's `--set-secrets` flag, or fetch at
  container start via the Secret Manager client library into environment
  variables before `exec`-ing the app.
- **Self-hosted**: HashiCorp Vault with the Vault Agent injecting
  environment variables, or at minimum a `backend.env` file at
  `/etc/nifty200-scanner/backend.env`, mode `600`, owned by root, only
  readable by the service user (this is what the provided systemd unit
  assumes — see step 8).

Whichever you choose, the application code doesn't change:
`Settings.from_env()` just reads `os.environ` — how those variables get
into the environment is entirely the orchestrator's job.

---

## 4. Database setup

1. Create the database and a dedicated user (do not use a superuser for
   the application):
   ```sql
   CREATE USER scanner_user WITH PASSWORD '...';
   CREATE DATABASE nifty200_scanner OWNER scanner_user;
   ```
2. Set `DATABASE_URL` in `backend/.env` to point at it:
   ```
   DATABASE_URL=postgresql+psycopg2://scanner_user:<password>@<host>:5432/nifty200_scanner
   ```
3. Initialize the schema:
   ```bash
   cd backend
   python -c "from app.db.session import get_engine, init_db; init_db(get_engine())"
   ```
4. Load the initial NIFTY 200 universe (see Phase 2):
   ```bash
   python -m app.universe.cli --file config/universe/nifty200_sample.csv
   ```
   Replace the sample file with your real, current constituent list before
   going live with anything beyond a demo.
5. **Connection pooling**: `DATABASE_POOL_SIZE`, `DATABASE_POOL_MAX_OVERFLOW`,
   `DATABASE_POOL_TIMEOUT_SECONDS`, and `DATABASE_STATEMENT_TIMEOUT_MS` are
   all configurable via `backend/.env` (see `.env.example`) — the defaults
   are conservative starting points, not tuned for your actual load; adjust
   based on real traffic once you have it.

---

## 5. Database backup strategy

See `deploy/backup.sh` for the actual script (pg_dump + gzip + local
retention) and its own header comments for the cron/systemd schedule and
restore procedure. Summary:
- Runs daily, after market close (20:30 UTC / 02:00 IST by default).
- Keeps 14 days of local backups by default (`RETENTION_DAYS`).
- **Ship backups off the host** (S3/GCS/equivalent) — a backup that lives
  only on the same disk as the database doesn't protect against host
  failure. This script does not do that upload step for you; add it, or
  prefer your cloud provider's managed automated backups (RDS/Cloud SQL
  snapshots) as the primary strategy and use this script for a portable
  secondary copy.
- **Test a real restore periodically.** An untested backup is not a
  verified backup.

---

## 6. Build and deploy — Docker path (recommended)

```bash
# From the repo root:
cp backend/.env.example backend/.env    # fill in real values (step 3)
mkdir -p secrets
echo -n "your-real-postgres-password" > secrets/postgres_password.txt
chmod 600 secrets/postgres_password.txt

docker compose up -d --build
docker compose logs -f backend   # watch the startup log
```

On startup, the backend runs `app.core.startup_checks.enforce_startup_checks()`
(see `app/main.py`'s `on_startup` handler) — **it will refuse to start** if
the configuration is dangerously inconsistent (e.g. `LIVE_TRADING_ENABLED=true`
with no broker credentials configured, or a production environment missing
`DATABASE_URL`/`SECRET_KEY`/proper CORS). If the container exits immediately,
check `docker compose logs backend` for a `FATAL startup configuration
problem` line — it tells you exactly what to fix.

---

## 7. Verify the deployment

```bash
curl https://your-domain.example.com/health
# {"status": "alive", "version": "..."}

curl https://your-domain.example.com/health/ready
# {"healthy": true, "components": [{"name": "database", "state": "ok", ...}]}

curl https://your-domain.example.com/metrics
# {"environment": "production", "live_trading_enabled": false, ...}
```

**Confirm `live_trading_enabled` reads `false`** in the `/metrics` response
unless you deliberately enabled it (see step 10). This is the fastest way
to catch a misconfigured deployment before it matters.

Check the WebSocket endpoint accepts connections (a full client isn't
needed — any WebSocket testing tool, e.g. `websocat wss://your-domain.example.com/ws`,
should connect successfully and the connection should show up in
`/metrics`'s `websocket_active_connections`).

---

## 8. Alternative: systemd (no Docker)

See `deploy/systemd/nifty200-backend.service` and
`deploy/systemd/nifty200-backup.{service,timer}`.

```bash
sudo useradd --system --home /opt/nifty200-scanner scanner
sudo mkdir -p /opt/nifty200-scanner /etc/nifty200-scanner /var/log/nifty200-scanner
sudo cp -r backend deploy /opt/nifty200-scanner/
cd /opt/nifty200-scanner/backend
sudo -u scanner python3 -m venv .venv
sudo -u scanner .venv/bin/pip install -r requirements.txt

# Real secrets go here, NOT in the repo's .env.example:
sudo cp .env.example /etc/nifty200-scanner/backend.env
sudo chmod 600 /etc/nifty200-scanner/backend.env
sudo chown root:root /etc/nifty200-scanner/backend.env
# edit /etc/nifty200-scanner/backend.env with real values

sudo cp /opt/nifty200-scanner/deploy/systemd/*.service /opt/nifty200-scanner/deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nifty200-backend.service
sudo systemctl enable --now nifty200-backup.timer
sudo systemctl status nifty200-backend.service
```

Put `deploy/nginx.conf.example` in front of it (adjust domain/cert paths)
for TLS termination and the WebSocket proxy config.

---

## 9. Frontend

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_BASE_URL=https://your-domain.example.com \
NEXT_PUBLIC_WS_URL=wss://your-domain.example.com/ws \
npm run build
npm start   # or deploy the .next build output to your hosting platform of choice
```

Remember: `NEXT_PUBLIC_*` variables are baked into the client-side JS
bundle at build time — never put a secret behind a `NEXT_PUBLIC_` prefix.
See `frontend/README.md` for the frontend's own remaining gaps (it has
never been run through a real build in this project's sandbox either).

---

## 10. Live trading — read this fully before touching it

**Live trading is disabled by default at every layer of this system**, and
that is deliberate, not an oversight to work around:
- `Settings().live_trading_enabled` defaults to `False`.
- `app.core.startup_checks` refuses to boot if `LIVE_TRADING_ENABLED=true`
  with no `BROKER_CREDENTIALS_PREFIX` set, in every environment.
- `app.brokers.safety.LiveTradingSafetyGate` requires the flag AND a
  genuinely-live broker adapter AND complete credentials AND (by default)
  risk-management approval — all independently, at every trade.
- There is currently **no real broker adapter implemented** in this
  codebase at all (by design — see the broker-integration phase). Even
  with every flag enabled, `create_broker_adapter()` in `app/brokers/factory.py`
  fails with `NotImplementedError` because nothing is registered.

To actually go live one day, in order:
1. Implement a real `BrokerAdapter` for your broker in its own module and
   call `register_live_broker()` from it.
2. Set real broker credentials via your secrets manager, under the prefix
   you configure in `BROKER_CREDENTIALS_PREFIX`.
3. Run extensively in paper mode first (the default) and review the
   backtest/paper-trading results honestly (see `QA_AUDIT_REPORT.md` and
   the Phase 12/13/15 reports).
4. Only then set `LIVE_TRADING_ENABLED=true`, and expect the startup and
   safety-gate checks above to hold you to a genuinely complete
   configuration, not just a flipped flag.

---

## 11. Post-deployment security checklist

- [ ] `backend/.env` (or your secrets manager equivalent) contains only
      real values, is not committed, and `.gitignore` covers it
- [ ] `CORS_ALLOWED_ORIGINS` is your real frontend domain, not `*`
- [ ] `FORCE_HTTPS=true`, and the proxy (nginx/load balancer) actually
      terminates TLS and redirects HTTP to HTTPS
- [ ] `/metrics` is not publicly reachable without restriction (see the
      nginx example's IP allowlist)
- [ ] Database port is not exposed publicly (see `docker-compose.yml`'s
      `127.0.0.1:5432:5432` binding)
- [ ] `SECRET_KEY` is a real random 32+ byte value, unique to this
      environment
- [ ] `LIVE_TRADING_ENABLED=false` unless you have deliberately, fully
      completed step 10
- [ ] A backup has actually run and been test-restored at least once
- [ ] `/health` and `/health/ready` both return successfully from outside
      the host
- [ ] Error monitoring (`SENTRY_DSN`) is configured if you want alerting on
      unhandled exceptions — it's optional but recommended for production
