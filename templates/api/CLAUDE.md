# __APP_NAME__ — API Template

Python FastAPI service. Five files, one job each.

## File map

| File | Job | Add here when you need to... |
|------|-----|------------------------------|
| `routes.py` | Structure — every endpoint listed in one place | Register a new URL path |
| `handlers.py` | Logic — what each request does | Add a new endpoint function |
| `models.py` | Data — request and response shapes | Define a new input or output type |
| `services.py` | Capabilities — DB queries, external calls | Add business logic or a DB operation |
| `config.py` | Config — env vars and settings | Add a new environment variable |
| `database.py` | DB session — do not modify | (rarely touched) |

## Adding a new endpoint (always this order)

1. **models.py** — define the request body and response shape
2. **services.py** — write the function that does the work
3. **handlers.py** — write the async function that calls the service, returns the model
4. **routes.py** — register the route with one line

## Idempotency rules

- **POST** that creates something: use `INSERT ... ON CONFLICT DO UPDATE` (upsert)
  — calling it twice with the same data produces the same result, no duplicate
- **PUT**: always a full replacement — same call, same result
- **Never** use auto-increment integers as external IDs — use `gen_random_uuid()`

## Error handling

- Services raise plain Python exceptions: `ValueError` (bad input), `RuntimeError` (system failure)
- Handlers catch and convert to `HTTPException`:
  - `ValueError` → 400
  - `PermissionError` → 403
  - `KeyError` / `LookupError` → 404
  - `RuntimeError` → 503
- Never raise `HTTPException` inside services

## Database migrations

```bash
# After changing a model, generate a migration:
alembic revision --autogenerate -m "describe what changed"
alembic upgrade head
```

## Health endpoints (do not remove)

- `GET /health` — liveness probe. Returns 200 if the process is running.
- `GET /ready` — readiness probe. Returns 200 if DB is reachable, 503 if not.
  Kubernetes will not send traffic until /ready returns 200.
