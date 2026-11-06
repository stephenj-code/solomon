/// config.rs — settings.
///
/// All environment variables read here via envy.
/// Add a new field + env var name when a new setting is needed.
/// Fields are public so handlers and services can read them.
use serde::Deserialize;

#[derive(Deserialize, Clone, Debug)]
pub struct Config {
    #[serde(default = "default_host")]
    pub host: String,

    #[serde(default = "default_port")]
    pub port: u16,

    #[serde(default)]
    pub database_url: String,

    #[serde(default)]
    pub debug: bool,
}

fn default_host() -> String { "0.0.0.0".to_string() }
fn default_port() -> u16 { 8000 }

impl Config {
    pub fn from_env() -> Self {
        envy::from_env().expect("failed to read config from environment")
    }
}
