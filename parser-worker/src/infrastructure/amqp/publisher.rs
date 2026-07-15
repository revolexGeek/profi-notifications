use async_trait::async_trait;
use lapin::options::BasicPublishOptions;
use lapin::{BasicProperties, Channel};

use super::codec;
use crate::application::ports::ResultPublisher;
use crate::domain::{ParseResult, ParserError, Result};

pub struct AmqpPublisher {
    channel: Channel,
    exchange: String,
    routing_key: String,
}

impl AmqpPublisher {
    pub fn new(
        channel: Channel,
        exchange: impl Into<String>,
        routing_key: impl Into<String>,
    ) -> Self {
        Self {
            channel,
            exchange: exchange.into(),
            routing_key: routing_key.into(),
        }
    }
}

#[async_trait]
impl ResultPublisher for AmqpPublisher {
    async fn publish(&self, result: &ParseResult) -> Result<()> {
        let payload = codec::encode_result(result)?;

        self.channel
            .basic_publish(
                self.exchange.clone().into(),
                self.routing_key.clone().into(),
                BasicPublishOptions::default(),
                &payload,
                BasicProperties::default().with_content_type("application/json".into()),
            )
            .await
            .map_err(publish_err)?
            .await
            .map_err(publish_err)?;

        Ok(())
    }
}

fn publish_err(error: lapin::Error) -> ParserError {
    ParserError::Publish(error.to_string())
}
