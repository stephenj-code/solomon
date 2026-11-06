# __APP_NAME__ — CronJob Template

Python batch job, run on a schedule. Five files, one job each.

## Schedule

Edit `k8s/cronjob.yaml`:
```yaml
schedule: "0 * * * *"   # cron syntax
```

Common schedules:
- `"0 * * * *"` — every hour at :00
- `"0 2 * * *"` — every day at 02:00 UTC
- `"*/15 * * * *"` — every 15 minutes
- `"0 0 * * 0"` — every Sunday at midnight

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

## Exit codes

- `0` → run completed — Kubernetes marks the Job Complete
- `1` → run failed — Kubernetes retries up to `backoffLimit` (default 2)

`concurrencyPolicy: Forbid` — if a previous run is still going, the new trigger is skipped.

## Idempotency

Design all steps to be safe to retry. Use upserts in services.py:

```python
INSERT INTO results (id, item_id, value)
VALUES (gen_random_uuid(), $1, $2)
ON CONFLICT (item_id) DO UPDATE SET value = EXCLUDED.value
```

## Triggering a run manually

```bash
# Trigger immediately without waiting for the schedule
kubectl create job --from=cronjob/__APP_NAME__ \
  __APP_NAME__-manual-$(date +%s) -n __NAMESPACE__

# Watch logs
kubectl logs -f -l job-name=__APP_NAME__-manual-... -n __NAMESPACE__
```

## HTTP calls

Use `httpx.AsyncClient` — not `requests` (synchronous):

```python
async with httpx.AsyncClient(timeout=30) as client:
    r = await client.get(url)
    r.raise_for_status()
    return r.json()
```
