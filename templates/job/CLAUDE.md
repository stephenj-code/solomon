# __APP_NAME__ — Job / CronJob Template

Python batch job. No HTTP server — just runs steps in sequence and exits.

- **`job`** — runs once and exits. Kubernetes marks it Complete or retries on failure.
- **`cronjob`** — runs on a schedule. Kubernetes wraps a Job in a CronJob spec.

The Python code is identical for both. Only the k8s manifest differs.

## Schedule (CronJob only)

Edit `k8s/cronjob.yaml`:
```yaml
schedule: "0 * * * *"   # cron syntax
```

Common schedules:
- `"0 * * * *"` — every hour at :00
- `"0 2 * * *"` — every day at 02:00 UTC
- `"*/15 * * * *"` — every 15 minutes
- `"0 0 * * 0"` — every Sunday at midnight

`concurrencyPolicy: Forbid` — if a previous run is still going, the new trigger is skipped.

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

- `0` → run completed — Kubernetes marks the Job Complete
- `1` → run failed — Kubernetes retries up to `backoffLimit`

## Idempotency

Design all steps to be safe to retry. If the job is retried after partial success,
it must not create duplicate data. Use upserts in services.py:

```python
INSERT INTO results (id, item_id, value)
VALUES (gen_random_uuid(), $1, $2)
ON CONFLICT (item_id) DO UPDATE SET value = EXCLUDED.value
```

## HTTP calls

Use `httpx.AsyncClient` — not `requests` (synchronous):

```python
async with httpx.AsyncClient(timeout=30) as client:
    r = await client.get(url)
    r.raise_for_status()
    return r.json()
```

## Secrets

`database_url` and `litellm_api_key` are `SecretStr`. Access the value with:
```python
settings.database_url.get_secret_value()
```
Never log these values. The `SecretStr` type masks them in repr/str automatically.

## Triggering a run manually in Kubernetes

```bash
# One-shot job
kubectl delete job __APP_NAME__ -n __NAMESPACE__ --ignore-not-found
kubectl apply -f k8s/job.yaml
kubectl logs -f job/__APP_NAME__ -n __NAMESPACE__

# CronJob — trigger immediately without waiting for the schedule
kubectl create job --from=cronjob/__APP_NAME__ \
  __APP_NAME__-manual-$(date +%s) -n __NAMESPACE__
kubectl logs -f -l job-name=__APP_NAME__-manual-... -n __NAMESPACE__
```
