# PyChat — Phase 1: Foundation
## Raw Sockets, Threads & Persistence

---

> **Project:** PyChat — a real-time chat system built from scratch in Python
> **Phase:** 1 of 3
> **Prerequisite:** Basic Python (functions, classes, loops). No prior networking knowledge needed.
> **Estimated effort:** 1–2 weeks

---

## Overview

In this phase you will build a working two-client chat system using **nothing but Python's standard library and a PostgreSQL database**. No frameworks, no abstractions — just raw TCP sockets and threads.

This is intentional. Before you ever touch FastAPI or WebSockets, you need to understand what a network connection actually *is*: a file descriptor, a byte stream, and a thread waiting on `recv()`. Every high-level framework you will ever use is secretly doing exactly what you are about to write by hand.

By the end of Phase 1, two people running separate terminals on their machines will be able to chat with each other through your server, and every message will survive a server restart because it lives in a real database.

---

## What You Will Learn

| Topic | Concept |
|---|---|
| Networking | TCP handshake, socket bind / listen / accept / send / recv |
| Concurrency | `threading.Thread`, `threading.Lock`, thread-safe shared state |
| Database basics | PostgreSQL table design, `psycopg2` connection pooling, parameterised queries |
| Robustness | Handling abrupt disconnects, graceful shutdown, error logging |
| Software design | Separating concerns — server logic vs. client logic vs. DB layer |

---

## Architecture

```
┌─────────────┐        TCP socket         ┌──────────────────┐        SQL        ┌─────────────┐
│  Client A   │ ◄────────────────────────► │                  │ ─────────────────► │             │
│  (CLI)      │                            │   TCP Server     │                    │  PostgreSQL │
│             │                            │   (server.py)    │ ◄───────────────── │             │
└─────────────┘        TCP socket          │                  │                    └─────────────┘
                                           │                  │
┌─────────────┐ ◄────────────────────────► │                  │
│  Client B   │                            └──────────────────┘
│  (CLI)      │
└─────────────┘
```

**Flow:**
1. The server starts and begins listening on a TCP port.
2. Client A connects, sends their username.
3. Client B connects, sends their username.
4. Client A sends a message → server receives it, writes it to PostgreSQL, then broadcasts it to all connected clients including Client B.
5. If Client A disconnects abruptly, the server detects the broken connection and removes them from the active list without crashing.

---

## Problem Statement

You are building a **broadcast chat server** — like a single chat room where everyone connected can see every message.

The server is the hub. It owns the list of active connections and is responsible for:
- Accepting new connections
- Reading messages from each client
- Broadcasting each message to every other connected client
- Writing every message to the database
- Cleaning up when a client disconnects

The client is a simple CLI program that:
- Connects to the server
- Prompts the user for a username
- Reads messages from stdin and sends them
- Receives and prints messages from the server in real time

The tricky part: sending and receiving happen **simultaneously**. You need two threads per client — one reading from the server (printing incoming messages), one reading from stdin (sending your own messages).

---

## Requirements

Requirements are labelled **[MUST]**, **[SHOULD]**, and **[BONUS]**.

- **[MUST]** — required for the phase to be considered complete
- **[SHOULD]** — expected; skip only if genuinely blocked
- **[BONUS]** — stretch goals that make the project significantly more impressive

### Server (`server.py`)

- **[MUST]** Accept multiple simultaneous TCP client connections using raw `socket` and `threading` — no `socketserver`, no frameworks.
- **[MUST]** Spawn a new `threading.Thread` for each connected client to handle that client's incoming messages.
- **[MUST]** Maintain a shared list/dict of all active client connections (socket + username).
- **[MUST]** When a message is received from one client, broadcast it to every other currently connected client.
- **[MUST]** Use a `threading.Lock` to protect all reads and writes to the shared client registry. In your `DESIGN.md` (see Deliverables), explain why this lock is necessary — what race condition does it prevent?
- **[MUST]** Detect when a client disconnects (abruptly or via `/quit`) and remove them from the registry without crashing the server.
- **[MUST]** Write every message to a PostgreSQL database (see schema below) before broadcasting it.
- **[SHOULD]** On a new client connecting, replay the last 20 messages from the database to them as a history catch-up.
- **[SHOULD]** Broadcast a `"[Server] username has joined/left the chat"` notification when clients connect or disconnect.
- **[SHOULD]** Support a `/quit` command from the client that cleanly closes the connection.
- **[BONUS]** Implement `/dm @username <message>` — a direct message routed only to the named client, not broadcast to everyone. Store it in the DB with `is_direct = TRUE`.
- **[BONUS]** Implement `/who` — server responds with a list of all currently connected usernames, sent only to the requesting client.

### Client (`client.py`)

- **[MUST]** Connect to the server via TCP socket.
- **[MUST]** Prompt the user for a username immediately after connecting and send it as the first message.
- **[MUST]** Use two threads: one dedicated to reading from the server socket and printing to stdout, one dedicated to reading stdin and sending to the server.
- **[MUST]** Handle server disconnection gracefully — print an error message and exit cleanly rather than crashing with a stack trace.
- **[SHOULD]** Prefix each sent message with the username and current timestamp before displaying it locally (the server will also broadcast the formatted version).
- **[SHOULD]** `/quit` exits both threads and closes the socket.

### Database

- **[MUST]** Use PostgreSQL. Do not use SQLite for this phase (the point is to learn real database tooling).
- **[MUST]** Connect using `psycopg2`. Use a simple connection pool (a `psycopg2.pool.ThreadedConnectionPool` is fine).
- **[MUST]** All DB writes are parameterised queries — no string concatenation for SQL. Understand why.
- **[SHOULD]** Create an index on `sent_at` to make the history replay query efficient.

---

## Database Schema

Create the following table. Save the DDL as `schema.sql` — it should be runnable with:

```bash
psql -U youruser -d pychat -f schema.sql
```

```sql
CREATE TABLE IF NOT EXISTS messages (
    id          SERIAL PRIMARY KEY,
    sender      VARCHAR(64)  NOT NULL,
    content     TEXT         NOT NULL,
    sent_at     TIMESTAMPTZ  DEFAULT NOW(),
    is_direct   BOOLEAN      DEFAULT FALSE,
    recipient   VARCHAR(64)  -- NULL for broadcast, username for DMs
);

CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at DESC);
```

**Think about:**
- Why `TIMESTAMPTZ` instead of `TIMESTAMP`? What happens when users are in different timezones?
- Why `SERIAL` for the primary key? What is it shorthand for?
- Why is `recipient` nullable? What does NULL mean in this context?

These are questions you should be able to answer by the end of this phase.

---

## Project Structure

Organise your project like this:

```
pychat/
├── server.py          # The TCP server
├── client.py          # The CLI client
├── db.py              # All database logic (connection pool, queries)
├── schema.sql         # DDL — run this once to set up the DB
├── requirements.txt   # psycopg2-binary, python-dotenv
├── .env               # DB credentials (never commit this)
├── .env.example       # Template with dummy values (commit this)
└── README.md          # Setup and run instructions
```

Keep `db.py` separate from `server.py`. This separation — business logic vs. data access — is a pattern you will use for the rest of the project and in every production system you ever build.

---

## Milestones

Work through these in order. Each one should produce something you can demo.

**Milestone 1 — Single-client echo server**
The server echoes back whatever any single client sends. No threading yet, no DB. Just `socket.bind`, `socket.listen`, `socket.accept`, `recv`, `send`. Get comfortable with the socket API.

**Milestone 2 — Multi-client broadcast**
Open two terminal windows. A message typed in one appears in both. You have solved the core networking problem. This requires threading.

**Milestone 3 — Username handling and clean disconnect**
Clients register a username on connect. Messages are formatted as `[HH:MM] username: message`. Disconnects are handled without crashing the server.

**Milestone 4 — PostgreSQL persistence**
Every message is written to the DB. Kill the server with `Ctrl+C`, restart it, connect a new client — they should see the last 20 messages replayed from the database. This proves persistence is working.

**Milestone 5 — Polish**
`/quit` works. `/who` works (or `/dm` if you chose that bonus). The README explains how to run everything from a clean machine.

---

## Guidelines & Hints

**On threading and the lock**

When two clients send messages at almost exactly the same time, two threads will both try to iterate over and write to the `clients` dict simultaneously. Without a lock, this is a data race — you might iterate over a list while another thread is modifying it, causing a crash or skipped messages. Always acquire the lock before touching shared state, and release it as soon as you're done.

```python
# Bad — no lock
for client_socket in clients:
    client_socket.sendall(message)

# Good — lock held only while iterating
with clients_lock:
    targets = list(clients.values())  # copy under the lock
# send outside the lock so you don't hold it during slow I/O
for sock in targets:
    try:
        sock.sendall(message)
    except Exception:
        pass  # handle dead sockets
```

**On the receive loop**

`socket.recv(N)` blocks until data arrives. A return value of `b""` (empty bytes) means the connection has been closed by the remote side. Always check for this:

```python
data = client_socket.recv(4096)
if not data:
    break  # client disconnected cleanly
```

**On the two-client-thread model**

Your client needs to do two things at once: wait for the user to type (blocking) and wait for messages from the server (also blocking). Run each in its own thread. Use `daemon=True` on the threads so they die automatically when the main thread exits.

**On database connections and threads**

Never share a single `psycopg2` connection between threads. Use `ThreadedConnectionPool` and check out / return a connection per operation. This is a real constraint of `psycopg2`.

---

## Deliverables

Submit the following:

| File | Description |
|---|---|
| `server.py` | Runnable with `python server.py`. Configurable port via env var. |
| `client.py` | Runnable with `python client.py`. Prompts for username on start. |
| `db.py` | Database layer — connection pool, `save_message()`, `get_recent_messages()`. |
| `schema.sql` | DDL — creates the `messages` table and index. |
| `requirements.txt` | `psycopg2-binary`, `python-dotenv` at minimum. |
| `.env.example` | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SERVER_PORT`. |
| `README.md` | Step-by-step: install deps, create DB, run schema, run server, run two clients. |
| `DESIGN.md` | Short doc (200–400 words): explain the threading model, why you need the lock, and one thing you would do differently if you were starting over. |

---

## How You Will Be Evaluated

- **Correctness:** Two clients can exchange messages in real time. Messages persist across server restarts.
- **Robustness:** Killing one client does not crash the server or affect the other client.
- **Code quality:** Functions are small and named clearly. `db.py` is cleanly separated from `server.py`.
- **Understanding:** `DESIGN.md` shows you actually understand the race condition the lock prevents — not just that you added one because you were told to.
- **Completeness:** All [MUST] requirements are met. At least one [SHOULD] is implemented.

---

## What Comes Next

Phase 2 takes everything you built here and rebuilds the server layer on top of **FastAPI and WebSockets** — the protocol that powers Discord, Slack, and most real-time web applications. You will also introduce a proper multi-table database schema with users, rooms, and authentication.

The raw socket knowledge from this phase is not wasted — it is exactly what will make Phase 2's abstractions make sense. When FastAPI says "WebSocket connection established", you will know what that actually means at the byte level.

---

*Phase 1 of 3 — PyChat assignment project*
