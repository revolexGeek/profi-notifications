use futures::StreamExt;
use lapin::Channel;
use lapin::options::{
    BasicAckOptions, BasicConsumeOptions, BasicNackOptions, BasicQosOptions, QueueDeclareOptions,
};
use lapin::types::FieldTable;
use tracing::{error, info};

use super::codec;
use crate::domain::{ParseRequest, ParserError, Result};

pub struct AmqpConsumer {
    channel: Channel,
    queue: String,
    prefetch: u16,
}

impl AmqpConsumer {
    pub fn new(channel: Channel, queue: impl Into<String>, prefetch: u16) -> Self {
        Self {
            channel,
            queue: queue.into(),
            prefetch,
        }
    }

    pub async fn run<H, F>(&self, handler: H) -> Result<()>
    where
        H: Fn(ParseRequest) -> F,
        F: Future<Output = Result<()>>,
    {
        self.channel
            .basic_qos(self.prefetch, BasicQosOptions::default())
            .await
            .map_err(queue_err)?;
        self.channel
            .queue_declare(
                self.queue.clone().into(),
                QueueDeclareOptions {
                    durable: true,
                    ..Default::default()
                },
                FieldTable::default(),
            )
            .await
            .map_err(queue_err)?;

        let mut consumer = self
            .channel
            .basic_consume(
                self.queue.clone().into(),
                "parser-worker".into(),
                BasicConsumeOptions::default(),
                FieldTable::default(),
            )
            .await
            .map_err(queue_err)?;
        info!(queue = %self.queue, "ожидаю запросы на парсинг");

        while let Some(delivery) = consumer.next().await {
            let delivery = delivery.map_err(queue_err)?;

            match codec::decode_request(&delivery.data) {
                Ok(request) => {
                    if let Err(error) = handler(request).await {
                        error!(%error, "обработка запроса не удалась");
                        delivery
                            .nack(BasicNackOptions::default())
                            .await
                            .map_err(queue_err)?;
                    } else {
                        delivery
                            .ack(BasicAckOptions::default())
                            .await
                            .map_err(queue_err)?;
                    }
                }
                Err(error) => {
                    error!(%error, "некорректное сообщение, отбрасываю");
                    delivery
                        .nack(BasicNackOptions::default())
                        .await
                        .map_err(queue_err)?;
                }
            }
        }

        Ok(())
    }
}

fn queue_err(error: lapin::Error) -> ParserError {
    ParserError::Queue(error.to_string())
}
