use anyhow::Result;

use parser_worker::infrastructure::{config::Config, telemetry};

#[tokio::main]
async fn main() -> Result<()> {
    let config = Config::from_env();
    telemetry::init(&config.log_level);

    tracing::info!(
        request_queue = %config.request_queue,
        result_routing_key = %config.result_routing_key,
        auth_grpc_addr = %config.auth_grpc_addr,
        "parser-worker запущен (каркас; логика — по TDD)"
    );

    Ok(())
}
