use anyhow::Result;
use tracing::info;

use parser_worker::application::ProcessParseRequest;
use parser_worker::infrastructure::amqp::{self, AmqpConsumer, AmqpPublisher};
use parser_worker::infrastructure::auth::GrpcCookieProvider;
use parser_worker::infrastructure::profi::ProfiBoardSource;
use parser_worker::infrastructure::{config::Config, telemetry};

#[tokio::main]
async fn main() -> Result<()> {
    let config = Config::from_env();
    telemetry::init(&config.log_level);

    info!(
        request_queue = %config.request_queue,
        result_routing_key = %config.result_routing_key,
        auth_grpc_addr = %config.auth_grpc_addr,
        "parser-worker запущен"
    );

    let cookies = GrpcCookieProvider::new(config.auth_grpc_addr.clone())?;
    let board = ProfiBoardSource::new(config.profi_graphql_url.clone());

    let connection = amqp::connect(&config.amqp_url).await?;
    let publish_channel = connection.create_channel().await?;
    let consume_channel = connection.create_channel().await?;

    let publisher = AmqpPublisher::new(
        publish_channel,
        config.result_exchange.clone(),
        config.result_routing_key.clone(),
    );
    let consumer = AmqpConsumer::new(
        consume_channel,
        config.request_queue.clone(),
        config.prefetch,
    );

    let use_case = ProcessParseRequest::new(cookies, board, publisher);

    // Liveness heartbeat for the container healthcheck: refresh /tmp/health
    // while the consumer loop runs. The process already exits on AMQP loss, so
    // a stale file signals a wedged event loop.
    tokio::spawn(async {
        let mut ticker = tokio::time::interval(std::time::Duration::from_secs(10));
        loop {
            ticker.tick().await;
            let _ = std::fs::write("/tmp/health", b"ok");
        }
    });

    tokio::select! {
        result = consumer.run(|request| async { use_case.execute(request).await.map(|_| ()) }) => result?,
        _ = tokio::signal::ctrl_c() => info!("получен сигнал остановки, завершаюсь"),
    }

    Ok(())
}
