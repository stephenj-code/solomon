/// services.rs — capabilities.
///
/// Business logic and database calls live here.
/// Handlers call services. Services never call handlers.
///
/// Idempotency pattern for writes:
///   INSERT ... ON CONFLICT DO UPDATE (upsert)
///   — same input always produces same result, never a duplicate.
///
/// Return Result<T, AppError> — handlers convert AppError to HTTP responses.
use sqlx::PgPool;

pub async fn check_database(pool: &PgPool) -> Result<String, String> {
    sqlx::query("SELECT 1")
        .execute(pool)
        .await
        .map(|_| "ok".to_string())
        .map_err(|e| format!("database unreachable: {e}"))
}

// Add domain service functions below:
//
// pub async fn create_item(
//     pool: &PgPool,
//     name: &str,
//     value: f64,
// ) -> Result<ItemRow, sqlx::Error> {
//     sqlx::query_as!(
//         ItemRow,
//         r#"
//         INSERT INTO items (id, name, value)
//         VALUES (gen_random_uuid(), $1, $2)
//         ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value
//         RETURNING id, name, value
//         "#,
//         name,
//         value,
//     )
//     .fetch_one(pool)
//     .await
// }
