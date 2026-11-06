/// handlers.rs — logic.
///
/// One async function per endpoint.
/// Handlers extract data from the request, call services, return responses.
/// No business logic here — that belongs in services.rs.
///
/// Axum extractors (function arguments) inject what the handler needs:
///   State(pool)  — the database pool from app state
///   Json(body)   — parsed request body
///   Path(id)     — URL path parameter (/items/:id → id)
use axum::{extract::State, http::StatusCode, Json};
use sqlx::PgPool;

use crate::models::{HealthResponse, ReadyResponse};
use crate::services;

pub async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok",
        version: env!("CARGO_PKG_VERSION"),
    })
}

pub async fn ready(
    State(pool): State<PgPool>,
) -> Result<Json<ReadyResponse>, (StatusCode, String)> {
    match services::check_database(&pool).await {
        Ok(db_status) => Ok(Json(ReadyResponse {
            status: "ok",
            database: db_status,
        })),
        Err(e) => {
            tracing::warn!("readiness check failed: {}", e);
            Err((StatusCode::SERVICE_UNAVAILABLE, e))
        }
    }
}

// Add domain handlers below:
//
// pub async fn create_item(
//     State(pool): State<PgPool>,
//     Json(body): Json<CreateItemRequest>,
// ) -> Result<Json<ItemResponse>, (StatusCode, String)> {
//     match services::create_item(&pool, &body.name, body.value).await {
//         Ok(row) => Ok(Json(ItemResponse { id: row.id, name: row.name, value: row.value })),
//         Err(e) => Err((StatusCode::INTERNAL_SERVER_ERROR, e.to_string())),
//     }
// }
