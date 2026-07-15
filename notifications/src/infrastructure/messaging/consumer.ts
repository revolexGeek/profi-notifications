import { ConsumerStatus } from 'rabbitmq-client';
import type { Connection, Consumer, Publisher } from 'rabbitmq-client';
import type { DeliveryDecision } from '../../application/delivery-decision';
import type { Logger } from '../../application/ports';
import type { SendNotificationUseCase } from '../../application/send-notification';
import type { PolicyConfig, RabbitConfig, TopologyConfig } from '../config/config';
import type { Metrics } from '../observability/metrics';
import { parseNotificationMessage } from './message-schema';
import { getAttemptCount } from './retry';

/** The message fields the handler needs. `AsyncMessage` is structurally compatible. */
export interface MessageLike {
  readonly body: unknown;
  readonly headers?: Record<string, unknown>;
  readonly routingKey?: string;
}

/** Abstraction over "put this message on the dead-letter exchange". */
export interface DeadLetterPublisher {
  publish(input: {
    readonly routingKey: string;
    readonly body: unknown;
    readonly headers: Record<string, unknown>;
    readonly reason: string;
    readonly category: string;
  }): Promise<void>;
}

export interface MessageHandlerDeps {
  readonly useCase: Pick<SendNotificationUseCase, 'execute'>;
  readonly deadLetterPublisher: DeadLetterPublisher;
  readonly metrics: Metrics;
  readonly logger: Logger;
  readonly mainQueue: string;
  readonly routingKey: string;
  readonly maxAttempts: number;
}

/**
 * Builds the message handler. It never throws: every message resolves to a
 * {@link ConsumerStatus}, so a message is only acknowledged after a successful
 * send or a confirmed handoff to the DLQ. Transient failures return DROP, which
 * dead-letters to the retry exchange (see {@link declareTopology}).
 */
export function createMessageHandler(
  deps: MessageHandlerDeps,
): (msg: MessageLike) => Promise<ConsumerStatus> {
  return async function handle(msg: MessageLike): Promise<ConsumerStatus> {
    deps.metrics.recordReceived();
    const attempt = getAttemptCount(msg.headers, deps.mainQueue);

    let decision: DeliveryDecision;
    try {
      const parsed = parseNotificationMessage(msg.body);
      if (!parsed.ok) {
        decision = { type: 'dead-letter', category: 'invalid-payload', reason: parsed.reason };
      } else {
        decision = await deps.useCase.execute(parsed.command, { attempt });
      }
    } catch (err) {
      const reason = err instanceof Error ? err.message : String(err);
      deps.logger.error('unhandled error while processing message', { reason });
      const attemptsMade = attempt + 1;
      decision =
        attemptsMade >= deps.maxAttempts
          ? { type: 'dead-letter', category: 'unexpected', reason: `unhandled error: ${reason}` }
          : { type: 'retry' };
    }

    return applyDecision(deps, msg, decision);
  };
}

async function applyDecision(
  deps: MessageHandlerDeps,
  msg: MessageLike,
  decision: DeliveryDecision,
): Promise<ConsumerStatus> {
  switch (decision.type) {
    case 'ack':
      deps.metrics.recordDelivered();
      return ConsumerStatus.ACK;

    case 'retry':
      deps.metrics.recordRetried();
      // BasicNack(requeue=false): the broker dead-letters this to the retry
      // exchange, which parks it before returning it to the main queue.
      return ConsumerStatus.DROP;

    case 'dead-letter':
      await deps.deadLetterPublisher.publish({
        routingKey: deps.routingKey,
        body: msg.body,
        headers: msg.headers ?? {},
        reason: decision.reason,
        category: decision.category,
      });
      deps.metrics.recordDeadLettered(decision.category);
      deps.logger.warn('message routed to the dead-letter queue', {
        category: decision.category,
        reason: decision.reason,
      });
      return ConsumerStatus.ACK;
  }
}

export interface NotificationConsumerConfig {
  readonly topology: TopologyConfig;
  readonly rabbit: RabbitConfig;
  readonly policy: PolicyConfig;
}

export interface NotificationConsumerDeps {
  readonly connection: Connection;
  readonly useCase: SendNotificationUseCase;
  readonly metrics: Metrics;
  readonly logger: Logger;
  readonly config: NotificationConsumerConfig;
}

export interface NotificationConsumer {
  readonly consumer: Consumer;
  readonly publisher: Publisher;
}

/**
 * Wires a resilient consumer + a publish-confirmed DLQ publisher onto a live
 * connection. Assumes {@link declareTopology} has already run (the consumer
 * re-declares only its own queue, with matching dead-letter arguments).
 */
export function createNotificationConsumer(deps: NotificationConsumerDeps): NotificationConsumer {
  const { connection, config, logger } = deps;
  const { topology, rabbit, policy } = config;

  const publisher = connection.createPublisher({
    confirm: true,
    maxAttempts: 3,
    exchanges: [{ exchange: topology.dlx, type: 'direct', durable: true }],
  });

  const deadLetterPublisher: DeadLetterPublisher = {
    async publish({ routingKey, body, headers, reason, category }) {
      await publisher.send(
        {
          exchange: topology.dlx,
          routingKey,
          durable: true,
          headers: {
            ...headers,
            'x-dead-letter-reason': reason,
            'x-dead-letter-category': category,
          },
        },
        body,
      );
    },
  };

  const handle = createMessageHandler({
    useCase: deps.useCase,
    deadLetterPublisher,
    metrics: deps.metrics,
    logger,
    mainQueue: topology.queue,
    routingKey: topology.routingKey,
    maxAttempts: policy.maxAttempts,
  });

  const consumer = connection.createConsumer(
    {
      queue: topology.queue,
      queueOptions: {
        durable: true,
        arguments: {
          'x-dead-letter-exchange': topology.retryExchange,
          'x-dead-letter-routing-key': topology.routingKey,
        },
      },
      qos: { prefetchCount: rabbit.prefetch },
      concurrency: rabbit.concurrency,
      // Our handler is total; an escaped throw should dead-letter, not hot-loop.
      requeue: false,
    },
    (msg) => handle(msg),
  );

  consumer.on('error', (err: unknown) => {
    logger.error('consumer error', {
      reason: err instanceof Error ? err.message : String(err),
    });
  });

  return { consumer, publisher };
}
