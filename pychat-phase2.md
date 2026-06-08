# PyChat — Phase 2: Production Core
## HTTP, WebSockets, Real Database Design & Authentication

---

> **Project:** PyChat — a real-time chat system built from scratch in Python
> **Phase:** 2 of 3
> **Prerequisite:** Phase 1 complete. You have a working TCP broadcast server and understand threading and raw sockets.
> **Estimated effort:** 2–3 weeks

---

## Overview

In Phase 1, you spoke TCP directly. In Phase 2, you speak the language the rest of the world uses: **HTTP and WebSockets**.

You will rebuild the server on top of **FastAPI** — a modern Python web framework — and replace the raw socket connection with a proper WebSocket upgrade. You will introduce real user accounts with password-based authentication, a relational database schema with multiple tables and foreign keys, and your first encounter with database transactions and row-level locking.

The CLI client stays, but it gets smarter — it speaks HTTP for auth and WebSockets for messaging.

This phase is where a junior developer starts to look like a mid-level engineer. The concepts you learn here — REST, JWTs, schema design, migrations, transactions — are the bread and butter of every backend system in production today.

---

## What You Will Learn

| Topic | Concept |
|---|---|
| Protocols | HTTP methods (GET/POST/PATCH/DELETE), status codes, request/response lifecycle |
| WebSockets | The upgrade handshake, frames, why WS exists vs. HTTP polling |
| FastAPI | Routing, dependency injection, Pydantic request/response schemas |
| Auth | Password hashing with `bcrypt`, JWT structure, bearer token flow |
| Database design | Foreign keys, junction tables, indexes, soft deletes, cursor-based pagination |
| Migrations | Alembic — versioned, repeatable schema changes |
| Transactions | ACID properties, `BEGIN / COMMIT / ROLLBACK`, `SELECT FOR UPDATE` |
| Async Python | `asyncio`, `async def`, `await`, the event loop, async vs. threading |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      CLI Client v2                        │
│                                                          │
│  1. POST /auth/register  ──────────────────────────────► │
│  2. POST /auth/login  ──────► receives JWT token         │
│  3. GET  /rooms  ──────────► lists available rooms       │
│  4. POST /rooms/{id}/join ─► joins a room                │
│  5. WS   /ws/{room_id}  ───► real-time messaging         │
└──────────────────────────────────────────────────────────┘
                          │ HTTP + WS
                          ▼
┌──────────────────────────────────────────────────────────┐
│                     FastAPI Server                        │
│                                                          │
│  ┌───────────────┐    ┌──────────────────────────────┐  │
│  │  REST routers  │    │   WebSocket connection mgr   │  │
│  │  /auth         │    │   rooms: {room_id → [socks]} │  │
│  │  /rooms        │    │   asyncio.Lock per room      │  │
│  │  /messages     │    └──────────────────────────────┘  │
│  └───────────────┘                   │                   │
│          │                           │                   │
│          └─────────────┬─────────────┘                   │
│                        ▼                                  │
│              SQLAlchemy async session                     │
└────────────────────────┬─────────────────────────────────┘
                         │ SQL
                         ▼
                  ┌─────────────┐
                  │  PostgreSQL  │
                  │  users       │
                  │  rooms       │
                  │  room_members│
                  │  messages    │
                  └─────────────┘
```

---

## Background: HTTP vs. WebSockets

**Why not just keep using raw TCP?**

Raw TCP gives you a connection, but nothing else. Every application that uses TCP has to invent its own protocol: how do you frame a message? How do you know where one message ends and the next begins? How does the server know who the client is?

HTTP solves this. It defines a standard request/response format, status codes, headers, and a connection lifecycle. It is stateless by design — every request stands alone.

**But HTTP is stateless. Chat is stateful. What gives?**

WebSockets solve this. A WebSocket starts as an HTTP request — the client sends an `Upgrade: websocket` header. If the server agrees, the connection is "upgraded": HTTP hands off the TCP connection to the WebSocket protocol, which supports two-way, full-duplex message passing. The connection stays open until one side closes it.

This is why Discord, Slack, and every real-time web app uses WebSockets. You will build the same thing.

---

## Problem Statement

You are extending PyChat from a single-room broadcast server into a **multi-room chat system with authentication**.

Users register once, log in to get a token, create or join rooms, then connect to a room's WebSocket endpoint to chat in real time. Multiple rooms run concurrently on the same server — a message in "general" does not appear in "engineering".

The server's WebSocket connection manager must track which sockets are connected to which room and correctly fan out messages only within each room. It must handle concurrent connections safely using `asyncio` locks.

---

## REST API Specification

### Auth

```
POST /auth/register
Body:  { "username": "alice", "email": "alice@example.com", "password": "secret" }
Response 201: { "id": 1, "username": "alice" }
Response 409: username or email already taken

POST /auth/login
Body:  { "username": "alice", "password": "secret" }
Response 200: { "access_token": "<jwt>", "token_type": "bearer" }
Response 401: invalid credentials
```

### Rooms

```
POST /rooms
Auth: Bearer token required
Body:  { "name": "engineering" }
Response 201: { "id": 3, "name": "engineering", "created_by": 1, "created_at": "..." }

GET /rooms
Auth: Bearer token required
Response 200: [ { "id": 1, "name": "general", "member_count": 12 }, ... ]

POST /rooms/{room_id}/join
Auth: Bearer token required
Response 200: { "message": "joined" }
Response 404: room not found
Response 409: already a member
```

### Messages

```
GET /rooms/{room_id}/messages?before=<msg_id>&limit=50
Auth: Bearer token required
Response 200: { "messages": [...], "has_more": true }

PATCH /messages/{message_id}
Auth: Bearer token required (must be message author)
Body:  { "content": "corrected text" }
Response 200: updated message object
Response 403: not the author
Response 404: not found

DELETE /messages/{message_id}
Auth: Bearer token required (must be message author)
Response 204: no content (soft delete — sets deleted_at)
Response 403: not the author
```

### WebSocket

```
WS /ws/{room_id}?token=<jwt>
```

Authenticate from the query param — WebSocket clients cannot send custom headers during the upgrade. On invalid/missing token, close with code 4001.

**Message envelope (JSON, both directions):**

```json
// Client → Server (send a message)
{ "type": "message", "content": "hello room!" }

// Server → Client (broadcast)
{ "type": "message", "id": 42, "sender": "alice", "content": "hello room!", "sent_at": "2025-01-15T10:23:00Z" }

// Server → Client (user joined)
{ "type": "event", "event": "user_joined", "username": "alice" }

// Server → Client (user left)
{ "type": "event", "event": "user_left", "username": "alice" }
```

---

## Requirements

### Authentication & Users
- **[MUST]** `POST /auth/register` hashes passwords with `bcrypt` before storing — never store plaintext.
- **[MUST]** `POST /auth/login` returns a signed JWT using `python-jose`. Token payload: `{ "sub": user_id, "exp": now + 24h }`.
- **[MUST]** All protected endpoints verify the JWT via a FastAPI dependency (`get_current_user`). A missing or invalid token returns 401.
- **[SHOULD]** Token expiry is enforced — expired tokens are rejected with a clear error message.

### Rooms & Membership
- **[MUST]** Full CRUD for rooms as specified above.
- **[MUST]** `room_members` junction table tracks who has joined what. A user can only join a room once (enforce with a unique constraint on `(room_id, user_id)`).
- **[MUST]** `GET /rooms/{room_id}/messages` uses cursor-based pagination via `before` (a message ID). Do not use `OFFSET` — understand why OFFSET is inefficient on large tables.

### WebSocket
- **[MUST]** WebSocket endpoint authenticates via `?token=<jwt>` query parameter.
- **[MUST]** Connection manager uses a `dict[int, list[WebSocket]]` keyed by `room_id`. Use an `asyncio.Lock` to protect it.
- **[MUST]** On message receive: validate, write to DB in a transaction, then broadcast to all room members.
- **[SHOULD]** If a client's socket is dead during broadcast (send raises an exception), remove them from the registry silently.

### Database & Transactions
- **[MUST]** Use Alembic for all schema changes. No raw DDL. Every schema change is a migration file.
- **[MUST]** Message insert + `room_members` update (if first message) must be wrapped in a single transaction. A failure at any point rolls back the whole operation.
- **[MUST]** Edit (`PATCH`) uses `SELECT ... FOR UPDATE` to lock the row before checking authorship and updating — prevents a race condition where two concurrent edits overwrite each other.
- **[SHOULD]** Soft delete: `DELETE /messages/{id}` sets `deleted_at = NOW()` rather than removing the row. `GET /rooms/{room_id}/messages` filters out soft-deleted messages.

### Rate Limiting
- **[SHOULD]** Enforce a per-user rate limit of 5 messages per second on the WebSocket endpoint. Implement a token bucket in memory (no Redis yet). Exceeding the limit sends a `{ "type": "error", "message": "rate limit exceeded" }` back to the offending client and does not broadcast.

### Bonus
- **[BONUS]** Read receipts: when a client connects to a room, it can send `{ "type": "ack", "message_id": 42 }` — broadcast `{ "type": "read", "user_id": 1, "message_id": 42 }` to the room.
- **[BONUS]** Typing indicator: client sends `{ "type": "typing" }` — server broadcasts `{ "type": "typing", "username": "alice" }` to other room members. Debounce: re-broadcast only if >2 s since last typing event from this user.

---

## Database Schema

All of these are created via Alembic migrations — there is no `schema.sql` in this phase.

```sql
-- Migration 001: users
CREATE TABLE users (
    id             SERIAL PRIMARY KEY,
    username       VARCHAR(64)  UNIQUE NOT NULL,
    email          VARCHAR(255) UNIQUE NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    created_at     TIMESTAMPTZ  DEFAULT NOW()
);

-- Migration 002: rooms and membership
CREATE TABLE rooms (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(128) UNIQUE NOT NULL,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE room_members (
    room_id    INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    joined_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (room_id, user_id)   -- composite PK prevents duplicates
);

-- Migration 003: messages
CREATE TABLE messages (
    id          SERIAL PRIMARY KEY,
    room_id     INTEGER REFERENCES rooms(id) ON DELETE CASCADE NOT NULL,
    sender_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    content     TEXT NOT NULL,
    sent_at     TIMESTAMPTZ DEFAULT NOW(),
    edited_at   TIMESTAMPTZ,          -- NULL if never edited
    deleted_at  TIMESTAMPTZ           -- NULL if not deleted (soft delete)
);

CREATE INDEX idx_messages_room_sent ON messages(room_id, sent_at DESC);
```

**Design questions to answer in `DESIGN.md`:**
- Why is `(room_id, user_id)` the primary key on `room_members` rather than a separate `id` column?
- What does `ON DELETE CASCADE` mean? What would happen without it?
- Why use cursor-based pagination (`WHERE id < :before_id`) instead of `LIMIT x OFFSET y`? What goes wrong with OFFSET at scale?
- What does `SELECT FOR UPDATE` actually do at the database level? What problem does it solve?

---

## Project Structure

```
pychat/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app creation, middleware, startup events
│   ├── config.py            # Settings from environment variables (pydantic BaseSettings)
│   ├── database.py          # SQLAlchemy engine, session factory, Base
│   ├── dependencies.py      # get_current_user, get_db FastAPI dependencies
│   ├── ws_manager.py        # WebSocket connection manager class
│   ├── models/
│   │   ├── user.py          # SQLAlchemy User model
│   │   ├── room.py          # SQLAlchemy Room, RoomMember models
│   │   └── message.py       # SQLAlchemy Message model
│   ├── schemas/
│   │   ├── auth.py          # Pydantic: RegisterRequest, LoginResponse, Token
│   │   ├── room.py          # Pydantic: RoomCreate, RoomResponse
│   │   └── message.py       # Pydantic: MessageCreate, MessageResponse
│   ├── routers/
│   │   ├── auth.py          # /auth/register, /auth/login
│   │   ├── rooms.py         # /rooms CRUD
│   │   ├── messages.py      # /rooms/{id}/messages, PATCH, DELETE
│   │   └── ws.py            # WS /ws/{room_id}
│   └── services/
│       ├── auth_service.py  # hash_password, verify_password, create_token
│       └── message_service.py  # save_message, get_messages (query logic)
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 001_create_users.py
│       ├── 002_create_rooms.py
│       └── 003_create_messages.py
├── client_v2.py             # Upgraded CLI client (HTTP auth + WS messaging)
├── alembic.ini
├── requirements.txt
├── .env
├── .env.example
├── README.md
└── DESIGN.md
```

The `models/` vs. `schemas/` split is important and often confusing at first:
- **Models** are SQLAlchemy classes that map to database tables.
- **Schemas** are Pydantic classes that define the shape of HTTP request/response bodies.
They are separate because what goes in the DB is not always the same as what you expose in your API.

---

## Milestones

**Milestone 1 — Skeleton + models committed**
FastAPI app runs. `GET /health` returns `{"status": "ok"}`. SQLAlchemy models created. `alembic upgrade head` creates all three tables in a fresh database.

**Milestone 2 — Auth endpoints live**
Register a user with curl. Log in, receive a JWT. Use the JWT to hit a protected route. Verify an expired/invalid token is rejected with 401.

**Milestone 3 — Room management REST API**
Create a room, list rooms, join a room. Verify the unique constraint on `room_members` prevents double-joining. Verify `GET /rooms/{id}/messages` returns paginated results.

**Milestone 4 — WebSocket messaging**
Open two terminals running `client_v2.py`. Both log in, join the same room, connect to `WS /ws/{room_id}`. Messages sent from one appear in the other. Invalid JWT on WS connect is rejected.

**Milestone 5 — Transactions verified**
Write a test (or manual procedure): start inserting a message, simulate a DB error mid-transaction (e.g., disconnect the DB, or raise an exception in your service), verify the message does not appear in the database. The partial write must roll back.

**Milestone 6 — Edit, delete, rate limiting**
`PATCH /messages/{id}` works for the author, returns 403 for anyone else. Soft-delete sets `deleted_at`. `GET /rooms/{id}/messages` does not return deleted messages. Sending 10 messages/second from one client triggers rate-limit errors.

---

## Guidelines & Hints

**On FastAPI dependency injection**

FastAPI's `Depends()` system is how you share logic across routes cleanly. Your `get_current_user` dependency should:
1. Extract the `Authorization: Bearer <token>` header (or the `?token=` query param for WebSocket).
2. Decode and verify the JWT.
3. Look up the user in the DB.
4. Return the user object — or raise `HTTPException(status_code=401)` if anything fails.

Any route that declares `current_user: User = Depends(get_current_user)` gets this automatically.

**On async and the event loop**

FastAPI uses `asyncio`. Your route handlers and WebSocket handlers should be `async def`. This means database calls must also be async — use `sqlalchemy.ext.asyncio` with an `AsyncSession`. Do not mix sync and async DB calls; it will deadlock.

If you need to run a CPU-bound or blocking operation, use `asyncio.run_in_executor()` to offload it to a thread pool.

**On the WebSocket connection manager**

The manager holds state (`dict[room_id → list[WebSocket]]`) that multiple concurrent connections modify. Use `asyncio.Lock` — not `threading.Lock` — because your code is async:

```python
class ConnectionManager:
    def __init__(self):
        self.rooms: dict[int, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id: int, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.rooms.setdefault(room_id, []).append(ws)

    async def broadcast(self, room_id: int, data: dict):
        async with self._lock:
            targets = list(self.rooms.get(room_id, []))
        for ws in targets:
            try:
                await ws.send_json(data)
            except Exception:
                await self.disconnect(room_id, ws)
```

**On transactions with SQLAlchemy async**

```python
async with db.begin():            # begins a transaction
    msg = Message(...)
    db.add(msg)
    # if anything raises here, the transaction rolls back automatically
# commit happens here on context manager exit
```

**On cursor-based pagination**

```sql
-- Bad (slow at large offsets)
SELECT * FROM messages WHERE room_id = 1 ORDER BY sent_at DESC LIMIT 50 OFFSET 500;

-- Good (always fast — uses the index)
SELECT * FROM messages
WHERE room_id = 1 AND id < :before_id AND deleted_at IS NULL
ORDER BY id DESC
LIMIT 50;
```

---

## Deliverables

| File/Directory | Description |
|---|---|
| `app/` | Full FastAPI application package as structured above |
| `alembic/` | Migration history — at least 3 migration files |
| `client_v2.py` | Upgraded CLI client — HTTP for auth, WS for messaging, renders room list |
| `requirements.txt` | All dependencies pinned (`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `python-jose[cryptography]`, `bcrypt`, `pydantic`, `pydantic-settings`) |
| `.env.example` | `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `SERVER_PORT` |
| `README.md` | Run instructions: how to create the DB, run migrations, start the server, use the client |
| `DESIGN.md` | 400–600 words: answer the four schema design questions above, explain the transaction strategy, describe the locking model for the WS manager |

---

## How You Will Be Evaluated

- **Correctness:** Two CLI clients in the same room exchange messages in real time. Auth is enforced on all routes.
- **Schema quality:** Foreign keys are correct. Indexes exist where queries need them. Soft-delete is implemented properly.
- **Transaction integrity:** A simulated mid-write failure does not leave partial data in the database.
- **Code structure:** The `models/schemas/routers/services` split is respected. No business logic in routers, no SQL in routers.
- **Understanding:** `DESIGN.md` gives thoughtful answers to the schema questions, not just definitions copied from a search engine.

---

## What Comes Next

Phase 3 takes this server and packages it for the real world. You will write a `Dockerfile`, a `docker-compose.yml` that spins up the entire stack with one command, and a minimal web UI that replaces the CLI client. You will also add structured logging and expose Prometheus metrics.

The end state of Phase 3 is a project where a recruiter can type `docker compose up` and see a working chat app in their browser.

---

*Phase 2 of 3 — PyChat assignment project*
