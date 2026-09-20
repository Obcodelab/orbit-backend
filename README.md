# Orbit Backend

Backend API for a SIWES (industrial training) project management and Kanban
tool — organizations, projects, tasks, and the people working on them.

## Stack

- **FastAPI** + **SQLAlchemy 2.0** (async) + **PostgreSQL**
- **Alembic** for migrations
- **Pydantic v2** for request/response schemas and settings
- **PyJWT** for access/refresh/reset tokens, with a DB-backed blacklist for revocation
- **uv** for dependency management, **ruff** for linting/formatting
- **slowapi** for rate limiting

## Project Structure

```
src/
├── core/          # config, database, security, auth dependency, rate limiting
├── infra/         # third-party service integrations
├── modules/
│   └── auth/      # apis / models / repositories / schemas / services
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
- 🚧 **Next up** — organizations, projects, and tasks (full Kanban CRUD
  with RBAC, comments, and activity logging).
- ⏳ **Planned** — file uploads/ingestion, real-time updates, an AI
  assistant.
