# Product Service

A small e-commerce product service built with Django and Django REST Framework.
It manages products and a nested category tree, and exposes a search endpoint
for filtering the catalogue.

The scope is deliberately narrow: few features, designed as if the service were
going to production — explicit indexes, pagination, input validation, defined
error formats, migrations and tests.

## Stack

| Component | Choice |
|---|---|
| Framework | Django 5.2 LTS |
| API | Django REST Framework |
| Database | PostgreSQL 16 |
| Search | PostgreSQL full-text + trigram similarity |
| API docs | drf-spectacular (OpenAPI 3 / Swagger UI) |
| Tests | pytest + pytest-django |
| Runtime | Docker Compose (Python 3.13) |

## API

Base prefix: `/api/v1/`

| Method | Path | Description |
|---|---|---|
| GET | `/products/` | List, search and filter |
| POST | `/products/` | Create |
| GET/PATCH/PUT | `/products/{sku}/` | Detail / update |
| DELETE | `/products/{sku}/` | Soft delete (`is_active=False`) |
| GET | `/categories/` | Flat, paginated list |
| GET | `/categories/tree/` | Nested category tree |
| POST | `/categories/` | Create |
| GET/PATCH/PUT | `/categories/{id}/` | Detail / update |
| DELETE | `/categories/{id}/` | `409` if children or products exist |

Products are addressed by their **SKU** rather than the numeric primary key —
it is the identifier clients already know, and it keeps the API decoupled from
the database schema.

Search is part of `GET /products/` via query parameters rather than a separate
`/search/` endpoint, so that filtering, ordering and pagination compose.

## Getting started

Requires Docker and `make`.

```sh
make init
```

This copies `.env.example` to `.env`, builds the images, starts the stack and
applies migrations. The API is then available at http://localhost:8000/api/v1/,
with the Swagger UI at http://localhost:8000/api/v1/docs/.

## Commands

Every task goes through the Makefile. Run `make` with no arguments for the full,
self-documenting list. The ones used most:

| Command | Description |
|---|---|
| `make init` | First-time setup — env file, build, start, migrate |
| `make up` / `make down` | Start / stop the stack |
| `make logs` | Follow the logs |
| `make migrate` | Apply migrations |
| `make seed` | Load demo data (idempotent) |
| `make superuser` | Create an admin user |
| `make shell` | Open a Django shell |
| `make test` | Run the test suite |
| `make lint` / `make format` | Run ruff |
| `make clean` | Stop the stack and drop volumes |

## Status

Work in progress. Currently in place:

- [x] Project skeleton, pinned to Django 5.2 on Python 3.13
- [ ] Docker Compose (Postgres + web) and Makefile
- [ ] Environment-based settings
- [ ] Product and Category models
- [ ] CRUD endpoints
- [ ] Search and filtering
- [ ] Test suite
- [ ] Seed data

## Design decisions and trade-offs

To be documented here as the implementation progresses — including what was
deliberately left out, and how it would be approached with more time.
