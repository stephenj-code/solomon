# __APP_NAME__ — Job Template

Python batch job. Runs once, exits 0 on success. Five files, one job each.

## File map

| File | Job | Add here when you need to... |
|------|-----|------------------------------|
| `app/job.py` | Structure — the steps, in order | Add a step or change the sequence |
| `app/steps.py` | Logic — what each step does | Add a new step function |
| `app/models.py` | Data — input/output shapes | Add a new data type |
| `app/services.py` | Capabilities — DB queries, HTTP calls | Add an external call |
| `app/config.py` | Config — env vars | Add a new environment variable |

## Adding a new step (always this order)

1. **models.py** — add input/output types if the step needs new data shapes
2. **services.py** — write the external call the step needs
3. **steps.py** — write the step function that calls the service
4. **job.py** — add the step call in the right sequence

## Running locally

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db python main.py
```

Or with a `.env` file:
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
LITELLM_API_KEY=sk-...
```

## Exit codes

- `0` → job completed — Kubernetes marks the Job Complete
- `1` → job failed — Kubernetes retries up to `backoffLimit` (default 3)

## Idempotency

Design all steps to be safe to retry. If the job is retried after partial success,
it must not create duplicate data. Use upserts in services.py:

```python
# SQL pattern:
INSERT INTO results (id, item_id, value)
VALUES (gen_random_uuid(), $1, $2)
ON CONFLICT (item_id) DO UPDATE SET value = EXCLUDED.value
```

## HTTP calls

Use `httpx.AsyncClient` — not `requests` (which is synchronous):

```python
async with httpx.AsyncClient(timeout=30) as client:
    r = await client.get(url)
    r.raise_for_status()
    return r.json()
```

## Triggering a job manually in Kubernetes

```bash
# Run the job now (one-shot)
kubectl delete job __APP_NAME__ -n __NAMESPACE__ --ignore-not-found
kubectl apply -f k8s/job.yaml
kubectl logs -f job/__APP_NAME__ -n __NAMESPACE__
```
