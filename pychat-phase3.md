# PyChat — Phase 3: Ship It
## Docker, Web UI & Observability

---

> **Project:** PyChat — a real-time chat system built from scratch in Python
> **Phase:** 3 of 3
> **Prerequisite:** Phase 2 complete. You have a working FastAPI + WebSocket server with authentication, a real database schema, and Alembic migrations.
> **Estimated effort:** 2–3 weeks

---

## Overview

A system that only runs on your laptop is not a system — it is a script. Phase 3 makes PyChat deployable by anyone, anywhere, with a single command.

You will containerise the entire stack using Docker and Docker Compose. You will replace the CLI client with a minimal but functional web UI. You will add structured logging and expose Prometheus metrics. And you will write integration tests that spin up a real database and prove the system works end to end.

The final deliverable is a GitHub repository that a recruiter, a senior engineer, or a potential co-founder can clone and run in under two minutes — and see a working, real-time chat application in their browser.

This is what "shipping" means.

---

## What You Will Learn

| Topic | Concept |
|---|---|
| Docker | Dockerfile syntax, multi-stage builds, image layers, `.dockerignore` |
| Docker Compose | Services, named volumes, environment variables, health checks, `depends_on` |
| Production server config | `uvicorn` workers, non-root user, proper shutdown handling |
| Web UI basics | React (or vanilla JS), `fetch()` for HTTP, the browser WebSocket API |
| Observability | Structured JSON logging, Prometheus metrics format, health check endpoints |
| Integration testing | `pytest` + `httpx`, test database isolation, async test fixtures |
| Deployment | Fly.io or Render free-tier deploy (bonus, but strongly recommended) |

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│  docker compose up                                                     │
│                                                                        │
│  ┌─────────────────────────┐         ┌──────────────────────────────┐ │
│  │   app (container)        │         │   db (container)              │ │
│  │                          │         │                              │ │
│  │  entrypoint.sh:          │  SQL    │  postgres:16-alpine          │ │
│  │    alembic upgrade head  │ ──────► │                              │ │
│  │    uvicorn app.main:app  │         │  named volume: postgres_data │ │
│  │                          │         │                              │ │
│  │  EXPOSE 8000             │         │  healthcheck: pg_isready     │ │
│  └──────────────┬───────────┘         └──────────────────────────────┘ │
│                 │ HTTP + WS                                             │
└─────────────────┼──────────────────────────────────────────────────────┘
                  │
          ┌───────▼────────┐
          │  Browser        │
          │  React / HTML   │
          │  Login page     │
          │  Room list      │
          │  Chat window    │
          └────────────────┘
```

**Data flow for a message sent from the browser:**
1. User types in the browser text box and presses Enter.
2. Browser JS sends `{ "type": "message", "content": "hello" }` over the WebSocket.
3. FastAPI receives it, writes to Postgres in a transaction, broadcasts to all room members.
4. All connected browsers receive the broadcast and append the message to the chat window.

---

## Part 1: Docker

### The Dockerfile

Write a **multi-stage Dockerfile** for the FastAPI application.

Multi-stage builds separate the build-time environment (where you install dependencies) from the runtime environment (what actually runs in production). The result is a smaller, cleaner image with no leftover build tools.

```dockerfile
# Stage 1: builder — install Python dependencies
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# Stage 2: runtime — copy only what's needed
FROM python:3.12-slim AS runtime
WORKDIR /app

# Non-root user for security
RUN useradd --create-home appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY entrypoint.sh .

RUN chmod +x entrypoint.sh && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
```

**`entrypoint.sh`:**
```bash
#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**`.dockerignore`** (always include this):
```
__pycache__/
*.pyc
*.pyo
.env
.venv
venv/
.git/
.gitignore
tests/
*.md
```

### Requirements — Dockerfile

- **[MUST]** Multi-stage build: `builder` + `runtime` stages as above.
- **[MUST]** Final image runs as a non-root user.
- **[MUST]** Final image is under 200 MB. Run `docker image ls pychat-app` to verify.
- **[MUST]** `.dockerignore` excludes `.env`, `__pycache__`, `.git`, and test files.
- **[MUST]** `entrypoint.sh` runs `alembic upgrade head` before starting the server.
- **[SHOULD]** `CMD` vs `ENTRYPOINT` — understand the difference and use the right one here (hint: `ENTRYPOINT` + `exec` for proper signal handling).

---

### The Docker Compose file

`docker-compose.yml` defines the entire stack as a reproducible multi-container application.

```yaml
version: "3.9"

services:

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      JWT_SECRET: ${JWT_SECRET}
      JWT_EXPIRE_MINUTES: ${JWT_EXPIRE_MINUTES:-1440}
    depends_on:
      db:
        condition: service_healthy
    restart: on-failure

volumes:
  postgres_data:
```

**`.env.example`:**
```
POSTGRES_USER=pychat
POSTGRES_PASSWORD=changeme
POSTGRES_DB=pychat
JWT_SECRET=change-this-to-a-long-random-string
JWT_EXPIRE_MINUTES=1440
```

### Requirements — Docker Compose

- **[MUST]** `app` and `db` services defined as above.
- **[MUST]** `db` has a `healthcheck` using `pg_isready`. `app` uses `depends_on: db: condition: service_healthy` — the server does not start until the database is ready.
- **[MUST]** Database data persisted in a named volume (`postgres_data`). Running `docker compose down` and `docker compose up` again must retain all messages and users.
- **[MUST]** All secrets and config passed via environment variables — nothing hardcoded in `docker-compose.yml` or app code.
- **[MUST]** `docker compose up --build` from a clean clone of the repo must produce a working application with no manual steps other than copying `.env.example` to `.env`.
- **[SHOULD]** A `ui` service that serves the web frontend (see Part 2). Can be as simple as an nginx container serving a built React app, or the app service serving static files directly.
- **[BONUS]** Add a `Makefile` with the following targets:

```makefile
dev:       ## Run server locally with hot reload (no Docker)
build:     ## Build Docker images
up:        ## Start the full stack
down:      ## Stop and remove containers
migrate:   ## Run Alembic migrations inside the running app container
logs:      ## Follow container logs
test:      ## Run the integration test suite
```

---

## Part 2: Web UI

Replace the CLI client with a minimal but fully functional browser-based chat UI. This does not need to be beautiful — it needs to work correctly and be readable.

### Required Screens

**Login / Register page**
- Two tabs or a toggle: "Log in" / "Register"
- Login form: username + password → calls `POST /auth/login` → stores JWT in memory (not localStorage — see note below)
- Register form: username + email + password → calls `POST /auth/register` → auto-login
- On success: redirect to the room list

**Room list page**
- Fetches `GET /rooms` and displays rooms as a list
- "Create room" button → input for room name → calls `POST /rooms`
- Clicking a room → calls `POST /rooms/{id}/join` (idempotent) → opens the chat view

**Chat view**
- Left sidebar: list of rooms the user has joined
- Main panel: message history (fetched via `GET /rooms/{id}/messages`), scrolled to bottom
- Input bar at the bottom: type a message, press Enter or click Send
- Messages appear in real time via WebSocket — no page reload required
- Each message shows: sender username, message content, timestamp
- Deleted messages show as `"[message deleted]"`

**Online indicator (should)**
When a user's WebSocket connects, they are "online". When they disconnect, they are "offline". Display a coloured dot next to usernames in the room. Derive this from the `user_joined` / `user_left` events the server already broadcasts.

### Technical Approach

**Option A — React with Vite (recommended)**
```bash
npm create vite@latest ui -- --template react
cd ui && npm install
```
Use the browser's built-in `WebSocket` class. Use `fetch()` with `Authorization: Bearer <token>` headers for REST calls. State management with `useState` and `useEffect` is sufficient — no Redux needed.

**Option B — Single HTML file (simpler)**
A single `index.html` with vanilla JS is completely acceptable. The browser WebSocket API and `fetch` are available without any build step:
```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/${roomId}?token=${token}`);
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    appendMessage(data);
};
```

### Note on JWT storage

Do not store the JWT in `localStorage` in a production app (XSS risk). For this assignment, storing it in a JavaScript variable (in-memory) is fine. It disappears on page refresh — users will need to log in again. That is acceptable for this project.

### Requirements — Web UI

- **[MUST]** Login and register work. Failed auth shows an error message.
- **[MUST]** Room list loads from the API. Clicking a room opens the chat view.
- **[MUST]** Messages in the chat view update in real time via WebSocket — no polling.
- **[MUST]** Message history loads on entering a room (last 50 messages).
- **[MUST]** Sending a message via the input bar works and the message appears immediately.
- **[SHOULD]** Online/offline dot per user based on WS connect/disconnect events.
- **[SHOULD]** Auto-scroll to the bottom when new messages arrive (unless the user has scrolled up).
- **[BONUS]** Infinite scroll upward — when the user scrolls to the top, load the next page of history using the cursor-based pagination API.
- **[BONUS]** Typing indicator — show `"alice is typing..."` using the typing events from Phase 2 bonus.

---

## Part 3: Observability

### Health Check

The server already needs `GET /health` for the Docker healthcheck. Make it meaningful:

```python
@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail={"status": "error", "database": str(e)})
```

A health check that does not actually check the database is almost useless.

### Structured Logging

Replace all `print()` statements and basic `logging` calls with structured JSON logs. Every log line should be valid JSON so it can be parsed by log aggregation tools (Datadog, Loki, etc.).

```python
import structlog

log = structlog.get_logger()

# Usage
log.info("message_saved", room_id=room_id, sender_id=user.id, message_id=msg.id)
log.warning("rate_limit_exceeded", user_id=user.id, room_id=room_id)
log.error("ws_send_failed", room_id=room_id, error=str(e))
```

Every log event should include: `timestamp`, `level`, `event`, and any relevant IDs as structured fields (not embedded in the message string).

### Prometheus Metrics

Expose `GET /metrics` in Prometheus exposition format using the `prometheus-client` library.

Implement these three gauges/counters:

```
# Active WebSocket connections per room
ws_connections_active{room_id="1"} 3

# Total messages processed since startup
messages_total{room_id="1"} 147

# DB query duration histogram (use the prometheus_client Histogram)
db_query_duration_seconds_bucket{le="0.01"} 1023
db_query_duration_seconds_bucket{le="0.05"} 1147
...
```

You do not need a full Prometheus + Grafana stack for this assignment. The `/metrics` endpoint just needs to return valid exposition format. You can verify it with `curl http://localhost:8000/metrics`.

### Requirements — Observability

- **[MUST]** `GET /health` checks the database connection and returns 503 if it is unhealthy.
- **[SHOULD]** All log output is structured JSON. No unstructured `print()` or bare `logging.info("some string")` calls in production code paths.
- **[SHOULD]** `GET /metrics` returns Prometheus-format metrics including `ws_connections_active` and `messages_total`.
- **[BONUS]** `db_query_duration_seconds` histogram tracking actual database query latency using SQLAlchemy event hooks.

---

## Part 4: Integration Tests

Integration tests verify that the entire system works together — real HTTP requests, real WebSocket connections, real database writes.

### Setup

Use `pytest` + `httpx` (async HTTP client) + `pytest-asyncio`.

Create a `conftest.py` that:
1. Spins up a test database (a separate Postgres DB or schema, not your dev DB).
2. Runs Alembic migrations against it before the test session.
3. Provides an `AsyncClient` configured against your FastAPI app.
4. Truncates all tables after each test (not the whole DB — just the rows).

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture
async def auth_client(client):
    await client.post("/auth/register", json={
        "username": "testuser", "email": "t@t.com", "password": "password123"
    })
    resp = await client.post("/auth/login", json={
        "username": "testuser", "password": "password123"
    })
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

### Required Tests

- **[MUST]** `test_register_and_login` — register a user, log in, receive a JWT.
- **[MUST]** `test_register_duplicate_username` — returns 409.
- **[MUST]** `test_login_wrong_password` — returns 401.
- **[MUST]** `test_create_room_and_list` — create a room, verify it appears in `GET /rooms`.
- **[MUST]** `test_join_room_twice` — returns 409 on the second join attempt.
- **[MUST]** `test_send_and_retrieve_message` — join a room, send a message via WS, verify it appears in `GET /rooms/{id}/messages`.
- **[SHOULD]** `test_rate_limit` — send 10 messages in rapid succession, verify the 6th+ receive rate-limit error events.
- **[SHOULD]** `test_soft_delete` — delete a message, verify it does not appear in message list but `deleted_at` is set in the DB.
- **[BONUS]** `test_edit_message_not_author` — try to edit another user's message, verify 403.

---

## Milestones

**Milestone 1 — Dockerfile working**
`docker build -t pychat-app .` completes. `docker run -e DATABASE_URL=... pychat-app` starts the server (it may fail to connect to DB, that is fine). Image is under 200 MB.

**Milestone 2 — Compose stack running**
`docker compose up --build` starts both services. Migrations run automatically. `curl http://localhost:8000/health` returns `{"status": "ok", "database": "connected"}`. `docker compose down && docker compose up` retains data in the volume.

**Milestone 3 — Web UI working end to end**
Open a browser to `http://localhost:8000` (or the UI port). Register, log in, create a room, send a message. Open a second browser window, log in as a different user, join the same room — messages appear in real time.

**Milestone 4 — Observability wired up**
`docker compose logs -f app` shows structured JSON. `curl http://localhost:8000/metrics` returns Prometheus-format output with at least `ws_connections_active` and `messages_total`.

**Milestone 5 — Tests passing**
`make test` (or `docker compose run app pytest tests/`) runs all integration tests and all pass against a test database.

**Milestone 6 — Clean clone demo**
Check out a clean copy of your repo into a new directory. Follow only the README instructions. The full application runs in under 2 minutes with no steps other than `cp .env.example .env && docker compose up`.

---

## The README (final version)

Your README is a first impression. Write it for two audiences: a developer who wants to run it, and a recruiter who wants to understand what you built.

Suggested structure:

```markdown
# PyChat

> Real-time multi-room chat system built from scratch in Python.
> WebSocket-based messaging, JWT authentication, PostgreSQL persistence.

## Live demo
[Link to deployed version on Fly.io / Render — if available]
[Screenshot of the UI]

## Tech stack
- **Backend:** FastAPI, SQLAlchemy (async), Alembic, asyncpg
- **Auth:** JWT (python-jose), bcrypt
- **Database:** PostgreSQL 16
- **Containerisation:** Docker, Docker Compose
- **Frontend:** React (Vite) / Vanilla JS
- **Testing:** pytest, httpx, pytest-asyncio

## Architecture
[Brief description or ASCII diagram — the one from this doc is fine]

## Run locally (Docker)
\`\`\`bash
git clone ...
cd pychat
cp .env.example .env   # edit if needed
docker compose up --build
\`\`\`
Open http://localhost:3000 (or 8000)

## Development setup (no Docker)
[Instructions for running server and UI locally without containers]

## Running tests
\`\`\`bash
docker compose run app pytest tests/ -v
\`\`\`

## Design decisions
[3–5 bullet points: why you chose these technologies, one thing you'd do differently]
```

---

## Bonus: Deploy to the Internet

This is the single highest-leverage thing you can do for the resume-worthiness of this project.

**Option A — Fly.io (recommended)**
```bash
brew install flyctl
flyctl auth login
flyctl launch         # detects Dockerfile automatically
flyctl postgres create
flyctl secrets set JWT_SECRET=...
flyctl deploy
```
Fly.io has a free tier sufficient for a demo app. It runs your Docker container directly.

**Option B — Render**
Connect your GitHub repo to Render. Set environment variables in the dashboard. Render will build and deploy on every push. Add a managed Postgres instance from the Render dashboard.

A live URL in your README turns a code project into a product.

---

## Final Deliverables

| File/Directory | Description |
|---|---|
| `Dockerfile` | Multi-stage build, non-root user, entrypoint.sh included |
| `.dockerignore` | Excludes `.env`, cache, git, test files |
| `docker-compose.yml` | `app` + `db` services, named volume, health checks |
| `.env.example` | All required environment variables with placeholder values |
| `entrypoint.sh` | Runs migrations then starts uvicorn |
| `ui/` | Web frontend — React (Vite) or single `index.html` |
| `tests/` | Integration test suite with `conftest.py` and all required tests |
| `Makefile` | `dev`, `build`, `up`, `down`, `migrate`, `logs`, `test` targets |
| `README.md` | Polished final README with screenshot, one-command setup, tech stack, design decisions |

---

## How You Will Be Evaluated

- **Deployability:** `docker compose up` from a clean clone works with no undocumented steps.
- **Correctness:** The web UI works end to end: register, login, create room, real-time messaging between two browser windows.
- **Data persistence:** `docker compose down && docker compose up` retains all data.
- **Observability:** Health check is meaningful. Logs are structured JSON. Metrics endpoint exists.
- **Tests:** Integration tests pass. They use a real database, not mocks.
- **README:** A senior engineer reading it should understand what was built, why, and how to run it in under 5 minutes.

---

## Looking Back at All Three Phases

You started by writing a raw TCP server. You now have a containerised, database-backed, WebSocket-powered chat application with a web UI, integration tests, and structured observability.

Here is everything you built and what it maps to in the real world:

| Phase 1 | Phase 2 | Phase 3 |
|---|---|---|
| Raw TCP sockets | HTTP + WebSocket protocol | Docker containerisation |
| `threading.Thread` | `asyncio` event loop | Docker Compose orchestration |
| `threading.Lock` | `asyncio.Lock` | Named volumes and secrets |
| Single `messages` table | 4-table relational schema | Structured logging |
| `psycopg2` direct | SQLAlchemy async ORM | Prometheus metrics |
| In-memory client list | JWT authentication | Integration tests |
| CLI interface | REST API | Web browser UI |

Every concept in this list appears in production systems at companies like Slack, Discord, GitHub, and Stripe — not as an abstraction you use, but as something you now understand from first principles.

---

*Phase 3 of 3 — PyChat assignment project*
