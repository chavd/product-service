# Product Service

A small e-commerce product service built with Django and Django REST Framework.
It manages products and a nested category tree, and exposes search and filtering
over the catalogue.

The scope is deliberately narrow: few features, built as if the service were
going to production — explicit indexes, pagination, input validation, defined
error formats, migrations, and tests for the part that carries the risk.

## Quickstart

Requires Docker and `make`.

```sh
make init
```

That copies `.env.example` to `.env`, builds the images, starts Postgres and
the web service, applies migrations and loads demo data. One command from a
fresh clone to a populated API.

| | |
|---|---|
| Swagger UI | http://localhost:8000/api/v1/docs/ |
| OpenAPI schema | http://localhost:8000/api/v1/schema/ |
| Django admin | http://localhost:8000/admin/ (`admin` / `admin`) |

Run `make` with no arguments for the full list of commands; `make test` runs
the suite, `make clean` tears everything down including the database volume.

## Stack

| Component | Choice | Why |
|---|---|---|
| Django 5.2 LTS | framework | LTS, supported into 2028 |
| Django REST Framework | API | ViewSets and routers remove boilerplate |
| PostgreSQL 16 | database | trigram search and recursive CTEs, neither of which SQLite has |
| django-filter | filtering | declarative FilterSets instead of if-chains in the view |
| drf-spectacular | API docs | OpenAPI 3 generated from the code, not maintained beside it |
| pytest + factory-boy | tests | readable fixtures, parametrisation |
| Docker Compose | runtime | Python 3.13, one command to start |

## API

Base prefix `/api/v1/`.

| Method | Path | Description |
|---|---|---|
| GET | `/products/` | List, search and filter |
| POST | `/products/` | Create |
| GET/PATCH/PUT | `/products/{sku}/` | Detail / update |
| DELETE | `/products/{sku}/` | Soft delete — sets `is_active=false`, returns 204 |
| GET | `/categories/` | Flat, paginated list |
| GET | `/categories/tree/` | The hierarchy as nested JSON |
| POST | `/categories/` | Create |
| GET/PATCH/PUT | `/categories/{id}/` | Detail / update |
| DELETE | `/categories/{id}/` | 409 if children or products still reference it |

### Search parameters

All optional, all combinable, combined with AND. Without any of them the
endpoint is simply the paginated catalogue.

| Parameter | Meaning |
|---|---|
| `q` | Fuzzy search over title, SKU and description |
| `title` | Substring match on the title only |
| `sku` | Exact SKU, case-insensitive |
| `price_min` / `price_max` | Price range, inclusive at both ends |
| `category` | Category id or slug |
| `include_descendants` | Include subcategories (default `true`) |
| `is_active` | Include soft-deleted products (default: only active) |
| `currency` | ISO-4217 code |
| `created_after` / `created_before` | Time window |
| `ordering` | `price`, `created_at`, `title`, `relevance`, each with `-` for descending |
| `page` / `page_size` | Pagination, page size capped at 100 |

## Example requests

Counts below are what the seeded demo data actually returns.

```sh
# Free text — 6 results
curl 'http://localhost:8000/api/v1/products/?q=laptop'

# The same query with transposed letters still finds them — 6 results
curl 'http://localhost:8000/api/v1/products/?q=lpatop'

# Combined filters, AND — 4 results
curl 'http://localhost:8000/api/v1/products/?q=aurora&price_min=1000&price_max=2000'

# Everything under a top-level category, recursively — 19 results
curl 'http://localhost:8000/api/v1/products/?category=electronics'

# The same category without recursion — 0 results, because no product
# is filed directly on the parent
curl 'http://localhost:8000/api/v1/products/?category=electronics&include_descendants=false'

# Soft-deleted products — 1 result
curl 'http://localhost:8000/api/v1/products/?is_active=false'

# Most expensive first
curl 'http://localhost:8000/api/v1/products/?ordering=-price'

# The category hierarchy
curl 'http://localhost:8000/api/v1/categories/tree/'
```

### Errors

Invalid input is rejected rather than quietly ignored, because a filter that
silently degrades to "no filter" hands the caller wrong results without saying
so.

```sh
curl '.../products/?price_min=1500&price_max=500'
# 400 {"price_min":["price_min must not be greater than price_max."]}

curl '.../products/?price_min=abc'
# 400 {"price_min":["Enter a number."]}

curl -X DELETE '.../categories/3/'
# 409 {"detail":"Category has 0 subcategories and 7 products and cannot be deleted."}
```

## Design decisions

**PostgreSQL, not SQLite.** The core of the assignment is search. Trigram
similarity and recursive CTEs do not exist in SQLite, so developing against it
would mean testing something other than what ships.

**Search is `GET /products/` with query parameters, not `POST /search/`.**
Searching is safe and idempotent, so GET is the correct method; results stay
cacheable and URLs stay shareable. A search without filters is just the full
list — two endpoints would mean two code paths and two pagination
implementations that drift apart.

**"Under a category" is recursive.** Asking for Electronics returns products
filed in Electronics → Computers → Laptops, resolved with a recursive CTE. A
plain `filter(category_id=...)` would return nothing at all for the demo data,
since products only sit on leaf categories.

**Trigram word similarity, not `ILIKE '%term%'`.** A leading wildcard cannot
use an index and gives every row the same score, so there is nothing to rank
by. Word similarity rather than plain similarity, because the latter compares
the term against the whole field and penalises short queries against long
titles — measured on this data, the typo `aurroa` scores 0.120 against
`Aurora Laptop Pro 14` that way and 0.429 the other.

Match thresholds are per field rather than one global cut-off, and each is
calibrated on measured values: a transposed-letter typo scores about 0.29 on a
title, unrelated SKUs resemble each other at 0.5 because identifiers are
structured, and a genuine description hit scores 1.0. One shared threshold
misbehaves at both ends.

**`Decimal`, never `float`, for money.** `0.1 + 0.2 <= 0.3` is `False` in
binary floating point — as a price filter that means a product at exactly
19.99 disappears from `price_max=19.99`. A bug that never shows up while
testing with round numbers.

**Soft delete.** Orders, carts and analytics may reference a product;
hard-deleting it tears holes in historical data. `DELETE` sets `is_active=false`
and the API hides such products unless asked.

**Validation sits at the layer that can guarantee it.** A non-negative price is
a database `CHECK` constraint, because bulk inserts and shell access bypass
application code; the field validator exists on top of it so the client gets a
400 with a readable message instead of a 500 from an integrity error.

**Indexes are partial.** The API always filters on `is_active=true`, so the
indexes carry `WHERE is_active` rather than indexing the boolean separately —
a plain index on a two-valued column is not used for the majority value.

## Trade-offs and deliberate omissions

**No authentication.** Not part of the assignment. Everything is open,
including writes.

**The category field is asymmetric.** Reads embed `category` as an object so
clients need no second request; writes take `category_id`. A GET response
therefore cannot be PUT back unchanged. Accepting `category` on write as well
would fix the round-trip and is a few lines — left out to keep one obvious
shape per direction.

**Price filtering assumes a single currency.** Comparing prices across
currencies is meaningless without conversion. `currency` can be filtered on,
but a range query over mixed currencies would return nonsense; the demo data is
euro-only. Real multi-currency support means prices as their own table.

**Two decimal places assume currencies with two minor units.** True for EUR,
USD and GBP; the Japanese yen has none and the Tunisian dinar has three.

**A soft-deleted product answers 404 on its detail route** unless
`?is_active=false` is passed. The filter applies to detail lookups too. That is
intended — the product does not exist for ordinary clients — but it surprises
on first contact.

**Unknown query parameters are ignored**, following normal HTTP behaviour;
invalid *values* are rejected with 400. Rejecting unknown names too would break
clients that append tracking parameters.

**A soft-deleted SKU stays taken.** Re-creating a product with the same SKU
fails. SKUs are globally unique identifiers, so this is intended rather than an
oversight.

**Category descendants are resolved in two round trips** — the CTE returns ids,
then the product query filters on them. A subquery would let Postgres plan both
at once; with a fourteen-node category tree the difference is not measurable.

**The container runs Django's development server.** Deliberate, for
auto-reload during the demo. Production would use gunicorn behind a reverse
proxy, and the entrypoint would not seed demo data.

**Images are stored on a local volume.** Production belongs in object storage
via `django-storages`, so the service stays stateless and can scale
horizontally.

## Tests

```sh
make test
```

51 tests, on two levels. The queryset tests exercise the search as plain query
code without HTTP; the API tests cover parameter mapping, status codes and
response shape. A failure at the lower level means the logic is wrong, a
failure only at the upper level means the mapping is.

Only the search is tested, which is what the assignment asks for. The fixture
tree files products two and three levels below the top category and none
directly on it, so the recursive category test genuinely fails without the CTE
instead of passing by accident.

Tests run against Postgres, not SQLite — otherwise trigram similarity and CTEs
would not exist and the tests would prove nothing about production.

## With more time

- **Authentication and permissions** — read-only for anonymous clients, writes
  behind a token.
- **Cursor pagination** for deep result sets. Page numbers get slow at large
  offsets and shift when rows are inserted mid-paging; they are the pragmatic
  choice for a catalogue with numbered pages, but not for an API consumed by
  machines.
- **A materialised path on categories** if the tree ever grows hot — one
  indexed `path__startswith` instead of a CTE, at the cost of updating a whole
  subtree when a node moves.
- **Caching** on the search endpoint, keyed on the query string, with
  invalidation on write.
- **Bulk import** for catalogue ingestion, which would need the SKU uniqueness
  to be enforced case-insensitively in the database rather than in `save()`.
- **Elasticsearch** once trigram search stops being enough — for stemming,
  synonyms and faceting. Not before; it is a lot of infrastructure to run for a
  catalogue this size.
