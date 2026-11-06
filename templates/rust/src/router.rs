/// router.rs — structure.
///
/// All routes registered here. Read this file to see every endpoint at a glance.
/// Pass app state (database pool, config) into the router so handlers can use it.
///
/// To add a new endpoint:
///   1. Write the handler in handlers.rs
///   2. Add one line here: .route("/v1/path", method(handler_fn))
use axum::{routing::get, Router};
use sqlx::PgPool;

use crate::handlers;

pub fn build(pool: PgPool) -> Router {
    Router::new()
        // Infrastructure endpoints — required by Kubernetes probes
        .route("/health", get(handlers::health))
        .route("/ready", get(handlers::ready))
        // Domain endpoints — add below
        // .route("/v1/items", post(handlers::create_item))
        // .route("/v1/items/:id", get(handlers::get_item))
        .with_state(pool)
}
