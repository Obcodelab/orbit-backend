# Orbit Backend

Backend API for a SIWES (industrial training) project management and Kanban
tool — organizations, projects, tasks, and the people working on them.

## Stack

- **FastAPI** + **SQLAlchemy 2.0** (async) + **PostgreSQL** (+ **pgvector**)
- **Alembic** for migrations
- **Pydantic v2** for request/response schemas and settings
- **PyJWT** for access/refresh/reset/download tokens, with a DB-backed blacklist for revocation
- **uv** for dependency management, **ruff** for linting/formatting
- **slowapi** for rate limiting
- **google-genai** (Gemini) for document embeddings
- **WebSockets** (native FastAPI/Starlette) for real-time task updates

## Project Structure

```
src/
├── core/          # config, database, security, auth dependency, rate
│                  # limiting, WebSocket connection manager, notifications
├── infra/         # third-party service integrations
├── modules/
│   ├── auth/          # apis / models / repositories / schemas / services
│   ├── organizations/ # orgs, membership, email-based invites
│   ├── projects/      # projects, members, activity log, dashboard
│   ├── tasks/          # tasks, subtasks, comments
│   ├── files/          # document upload/download/delete, storage backends
│   ├── ai/             # embeddings, chunking, extraction, ingestion pipeline
│   └── realtime/       # WS /ws/{project_id} route
└── main.py
alembic/           # migrations
tests/             # mirrors src/modules, tested against a real Postgres test DB
```

Each module under `src/modules/` is self-contained: its own models,
repositories, schemas, services, and API routes. `core/auth.py` is the one
place core code is allowed to import from a module (the `get_current_user`
dependency).

## Getting Started

1. Install dependencies:
   ```
   make install
   ```
2. Copy `.env.example` to `.env` and fill in real values (a local Postgres
   connection string, a generated `JWT_SECRET_KEY`, Google OAuth
   credentials if you're testing that flow).
3. Run migrations:
   ```
   make migrate
   ```
4. Start the dev server:
   ```
   make run
   ```

API docs are served at `/docs` when `ENVIRONMENT=local`.

## Testing

Tests run against a real Postgres database (`TEST_DATABASE_URL`), not
mocks or SQLite — each test runs inside a transaction that's rolled back
afterward.

```
make test
make test args="-k test_auth"
```

## Common Commands

Run `make help` for the full list — `makemigration`, `migrate`,
`rollback`, `format`, `lint`, among others.

## Current Status

- ✅ **Auth** — registration with email verification, login, JWT
  access/refresh tokens with revocation, forgot/reset password, change
  password, profile management under `/account`, Google OAuth (PKCE).
- ✅ **Organizations & Projects** — org/project CRUD, membership, RBAC,
  email-based invites, project dashboard, activity timeline.
- ✅ **Tasks** — full Kanban CRUD, subtasks, multiple assignees, status
  transitions, comments, activity logging, pagination/sort/search.
- ✅ **Files & AI Ingestion** — upload/list/get/download/delete with
  swappable local/Supabase storage (Supabase backend is a stub), content-
  hash dedup, background ingestion (extract → chunk → embed → pgvector).
- ✅ **Real-time** — per-project WebSocket broadcasts on task events, plus
  per-user push notifications with a mocked email fallback.
- ⏳ **Planned** — AI assistant (retrieval + citation-backed chat over
  ingested documents), full rate-limit coverage for AI endpoints,
  deployment.
