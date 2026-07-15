import type { Connection } from 'rabbitmq-client';
import type { TopologyConfig } from '../config/config';

/**
 * Declares the full exchange/queue topology (idempotent). Layout:
 *
 *   producer ──▶ [exchange] ──▶ (main queue)
 *                                  │ nack(requeue=false)
 *                                  ▼
 *                            [retry exchange] ──▶ (retry queue, TTL)
 *                                                    │ message expires
 *                                                    ▼ dead-letters back to
 *                                              [exchange] ──▶ (main queue)
 *
 *   exhausted / permanent ──(app publishes)──▶ [dlx] ──▶ (dead-letter queue)
 *
 * The main queue dead-letters to the retry exchange; the retry queue holds a
 * message for `retryDelayMs` then dead-letters it back to the main exchange.
 * Terminal failures are published straight to the DLX by the application.
 */
export async function declareTopology(
  connection: Connection,
  topology: TopologyConfig,
): Promise<void> {
  const { exchange, queue, routingKey, retryExchange, retryQueue, dlx, dlq, retryDelayMs } =
    topology;

  // Exchanges
  await connection.exchangeDeclare({ exchange, type: 'direct', durable: true });
  await connection.exchangeDeclare({ exchange: retryExchange, type: 'direct', durable: true });
  await connection.exchangeDeclare({ exchange: dlx, type: 'direct', durable: true });

  // Main work queue: rejected messages dead-letter to the retry exchange.
  await connection.queueDeclare({
    queue,
    durable: true,
    arguments: {
      'x-dead-letter-exchange': retryExchange,
      'x-dead-letter-routing-key': routingKey,
    },
  });
  await connection.queueBind({ queue, exchange, routingKey });

  // Retry queue: parks a message for retryDelayMs, then dead-letters it back to
  // the main exchange for another attempt.
  await connection.queueDeclare({
    queue: retryQueue,
    durable: true,
    arguments: {
      'x-message-ttl': retryDelayMs,
      'x-dead-letter-exchange': exchange,
      'x-dead-letter-routing-key': routingKey,
    },
  });
  await connection.queueBind({ queue: retryQueue, exchange: retryExchange, routingKey });

  // Dead-letter queue: terminal storage for poison / exhausted messages.
  await connection.queueDeclare({ queue: dlq, durable: true });
  await connection.queueBind({ queue: dlq, exchange: dlx, routingKey });
}
