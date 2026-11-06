mod config;
mod handlers;
mod models;
mod router;
mod services;

use sqlx::postgres::PgPoolOptions;

#[tokio::main]
async fn main() {
    let cfg = config::Config::from_env();

    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&cfg.database_url)
        .await
        .expect("failed to connect to database");

    let app = router::build(pool);

    let addr = format!("{}:{}", cfg.host, cfg.port);
    println!("listening on {addr}");

    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
