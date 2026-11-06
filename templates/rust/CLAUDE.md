# __APP_NAME__ — Rust Template

Axum + Tokio web service. Five files, one job each.

## File map

| File | Job | Add here when you need to... |
|------|-----|------------------------------|
| `src/router.rs` | Structure — every route in one place | Register a new URL path |
| `src/handlers.rs` | Logic — what each request does | Add a new handler function |
| `src/models.rs` | Data — request and response types | Add a new data shape |
| `src/services.rs` | Capabilities — DB queries, external calls | Add business logic or a DB query |
| `src/config.rs` | Config — env vars | Add a new environment variable |

## Adding a new endpoint (always this order)

1. **models.rs** — add `#[derive(Deserialize)]` struct for request, `#[derive(Serialize)]` for response
2. **services.rs** — write the async function that does the work
3. **handlers.rs** — write the async handler that calls the service
4. **router.rs** — add one `.route(...)` line

## Rust concepts for reference

**Ownership** — every value has one owner. When the owner goes out of scope, the value is dropped.
To share without moving: borrow with `&` (read) or `&mut` (write).

**Result<T, E>** — Rust's error type. Either `Ok(value)` or `Err(error)`. Use `?` to propagate errors up.
```rust
let value = might_fail()?;  // if Err, return early with that error
```

**async/await** — same concept as Python/TypeScript. Functions marked `async` return a Future.
Call with `.await` to run it. Tokio is the runtime that drives them.

**derive macros** — `#[derive(Serialize, Deserialize)]` auto-generates JSON conversion code.
Add this to any struct you want to send/receive as JSON.

**State extractor** — Axum injects shared state (the DB pool) into handlers automatically:
```rust
pub async fn my_handler(State(pool): State<PgPool>) -> ...
```

## Idempotency pattern

```sql
INSERT INTO items (id, name, value)
VALUES (gen_random_uuid(), $1, $2)
ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value
RETURNING id, name, value
```
Use `sqlx::query_as!()` macro — it checks queries against the DB at compile time.

## Database migrations

```bash
sqlx migrate add create_items_table   # creates migrations/TIMESTAMP_create_items_table.sql
# edit the SQL file
sqlx migrate run                       # applies pending migrations
```
