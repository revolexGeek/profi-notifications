mod codec;
mod consumer;
mod publisher;

pub use consumer::AmqpConsumer;
pub use publisher::AmqpPublisher;

use lapin::{Connection, ConnectionProperties};

use crate::domain::{ParserError, Result};

pub async fn connect(url: &str) -> Result<Connection> {
    Connection::connect(url, ConnectionProperties::default())
        .await
        .map_err(|error| ParserError::Queue(error.to_string()))
}
