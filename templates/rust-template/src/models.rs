/// models.rs — data shapes.
///
/// All request and response types defined here.
/// Serde derives handle JSON serialisation automatically.
/// Handlers and services import from here — never define types inline.
use serde::{Deserialize, Serialize};

#[derive(Serialize)]
pub struct HealthResponse {
    pub status: &'static str,
    pub version: &'static str,
}

#[derive(Serialize)]
pub struct ReadyResponse {
    pub status: &'static str,
    pub database: String,
}

// Add your domain types below:
//
// #[derive(Deserialize)]
// pub struct CreateItemRequest {
//     pub name: String,
//     pub value: f64,
// }
//
// #[derive(Serialize)]
// pub struct ItemResponse {
//     pub id: String,
//     pub name: String,
//     pub value: f64,
// }
