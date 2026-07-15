import { describe, expect, it } from 'bun:test';
import { ConsumerStatus } from 'rabbitmq-client';
import type { Connection } from 'rabbitmq-client';
import { PermanentDeliveryError } from '../../application/errors';
import { SendNotificationUseCase } from '../../application/send-notification';
import type { PolicyConfig, RabbitConfig, TopologyConfig } from '../config/config';
import { MetricsRegistry } from '../observability/metrics';
import { createSilentLogger, StubSender } from '../../../tests/support/fakes';
import { createNotificationConsumer } from './consumer';

const topology: TopologyConfig = {
  exchange: 'notifications',
  queue: 'notifications',
  routingKey: 'notify',
  retryExchange: 'notifications.retry',
  retryQueue: 'notifications.retry',
  dlx: 'notifications.dlx',
  dlq: 'notifications.dlq',
  retryDelayMs: 30_000,
};
const rabbit: RabbitConfig = { url: 'amqp://x', prefetch: 10, concurrency: 5 };
const policy: PolicyConfig = { maxAttempts: 5 };

interface SentRecord {
  envelope: Record<string, unknown>;
  body: unknown;
}

type Handler = (msg: unknown) => Promise<ConsumerStatus>;

function fakeConnection() {
  const sent: SentRecord[] = [];
  let publisherProps: Record<string, unknown> | undefined;
  let consumerProps: Record<string, unknown> | undefined;
  let handler: Handler | undefined;

  const publisher = {
    send: async (envelope: Record<string, unknown>, body: unknown) => {
      sent.push({ envelope, body });
    },
    close: async () => {},
    on: () => publisher,
  };
  const consumer = {
    on: () => consumer,
    close: async () => {},
    start: () => {},
  };
  const connection = {
    createPublisher: (props: Record<string, unknown>) => {
      publisherProps = props;
      return publisher;
    },
    createConsumer: (props: Record<string, unknown>, cb: Handler) => {
      consumerProps = props;
      handler = cb;
      return consumer;
    },
  };

  return {
    connection: connection as unknown as Connection,
    sent,
    getPublisherProps: () => publisherProps,
    getConsumerProps: () => consumerProps,
    invoke: (msg: unknown): Promise<ConsumerStatus> => handler!(msg),
  };
}

function build(behavior: () => void = () => {}) {
  const fake = fakeConnection();
  const useCase = new SendNotificationUseCase({
    sender: new StubSender(behavior),
    logger: createSilentLogger(),
    maxAttempts: policy.maxAttempts,
  });
  const result = createNotificationConsumer({
    connection: fake.connection,
    useCase,
    metrics: new MetricsRegistry(),
    logger: createSilentLogger(),
    config: { topology, rabbit, policy },
  });
  return { fake, result };
}

describe('createNotificationConsumer wiring', () => {
  it('creates a publish-confirmed publisher that declares the DLX', () => {
    const { fake } = build();

    expect(fake.getPublisherProps()).toMatchObject({
      confirm: true,
      exchanges: [{ exchange: 'notifications.dlx', type: 'direct', durable: true }],
    });
  });

  it('creates the consumer with retry dead-letter arguments and no auto-requeue', () => {
    const { fake } = build();

    expect(fake.getConsumerProps()).toMatchObject({
      queue: 'notifications',
      qos: { prefetchCount: 10 },
      concurrency: 5,
      requeue: false,
      queueOptions: {
        durable: true,
        arguments: {
          'x-dead-letter-exchange': 'notifications.retry',
          'x-dead-letter-routing-key': 'notify',
        },
      },
    });
  });

  it('returns the consumer and publisher handles', () => {
    const { result } = build();

    expect(result.consumer).toBeDefined();
    expect(result.publisher).toBeDefined();
  });

  it('publishes to the DLX with reason/category headers when dead-lettering', async () => {
    const { fake } = build(() => {
      throw new PermanentDeliveryError('nope');
    });

    const status = await fake.invoke({
      body: { text: 'hi' },
      headers: { 'x-trace': 'abc' },
      routingKey: 'notify',
    });

    expect(status).toBe(ConsumerStatus.ACK);
    expect(fake.sent).toHaveLength(1);
    expect(fake.sent[0]!.body).toEqual({ text: 'hi' });
    expect(fake.sent[0]!.envelope).toMatchObject({
      exchange: 'notifications.dlx',
      routingKey: 'notify',
      durable: true,
      headers: {
        'x-trace': 'abc',
        'x-dead-letter-category': 'permanent',
        'x-dead-letter-reason': 'nope',
      },
    });
  });

  it('does not publish to the DLX on a successful delivery', async () => {
    const { fake } = build();

    const status = await fake.invoke({ body: { text: 'hi' } });

    expect(status).toBe(ConsumerStatus.ACK);
    expect(fake.sent).toHaveLength(0);
  });
});
