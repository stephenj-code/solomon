mod config;
mod handlers;
mod models;
mod router;
mod services;

use sqlx::postgres::PgPoolOptions;

#[tokio::main]
async fn main() {
    // Initialise structured logging. Level controlled by RUST_LOG env var.
    // Default: INFO. Set RUST_LOG=debug for verbose output.
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    let cfg = config::Config::from_env();

    // database_url is intentionally not logged — it contains credentials
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&cfg.database_url)
        .await
        .expect("failed to connect to database");

    let app = router::build(pool);

    let addr = format!("{}:{}", cfg.host, cfg.port);
    tracing::info!("listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
