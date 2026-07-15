use async_trait::async_trait;

use crate::application::ports::ResultPublisher;
use crate::domain::{ParseResult, Result};

pub struct AmqpPublisher {
    exchange: String,
    routing_key: String,
}

impl AmqpPublisher {
    pub fn new(exchange: impl Into<String>, routing_key: impl Into<String>) -> Self {
        Self {
            exchange: exchange.into(),
            routing_key: routing_key.into(),
        }
    }
}

#[async_trait]
impl ResultPublisher for AmqpPublisher {
    async fn publish(&self, result: &ParseResult) -> Result<()> {
        let _ = (&self.exchange, &self.routing_key, result);
        todo!("публикация ParseResult в RabbitMQ")
    }
}

pub struct AmqpConsumer {
    amqp_url: String,
    queue: String,
    prefetch: u16,
}

impl AmqpConsumer {
    pub fn new(amqp_url: impl Into<String>, queue: impl Into<String>, prefetch: u16) -> Self {
        Self {
            amqp_url: amqp_url.into(),
            queue: queue.into(),
            prefetch,
        }
    }

    pub async fn run(&self) -> Result<()> {
        let _ = (&self.amqp_url, &self.queue, self.prefetch);
        todo!("consume parse.requests -> ProcessParseRequest -> ack")
    }
}
