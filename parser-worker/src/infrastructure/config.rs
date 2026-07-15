#[derive(Debug, Clone)]
pub struct Config {
    pub amqp_url: String,
    pub request_queue: String,
    pub result_exchange: String,
    pub result_routing_key: String,
    pub prefetch: u16,
    pub auth_grpc_addr: String,
    pub profi_graphql_url: String,
    pub log_level: String,
}

impl Config {
    pub fn from_env() -> Self {
        Self {
            amqp_url: env("PARSER_AMQP_URL", "amqp://guest:guest@127.0.0.1:5672/%2f"),
            request_queue: env("PARSER_REQUEST_QUEUE", "parse.requests"),
            result_exchange: env("PARSER_RESULT_EXCHANGE", ""),
            result_routing_key: env("PARSER_RESULT_ROUTING_KEY", "parse.results"),
            prefetch: env_u16("PARSER_PREFETCH", 8),
            auth_grpc_addr: env("PARSER_AUTH_GRPC_ADDR", "http://127.0.0.1:50051"),
            profi_graphql_url: env("PARSER_PROFI_GRAPHQL_URL", "https://profi.ru/graphql"),
            log_level: env("LOG_LEVEL", "info"),
        }
    }
}

fn env(key: &str, fallback: &str) -> String {
    std::env::var(key).unwrap_or_else(|_| fallback.to_string())
}

fn env_u16(key: &str, fallback: u16) -> u16 {
    std::env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(fallback)
}
