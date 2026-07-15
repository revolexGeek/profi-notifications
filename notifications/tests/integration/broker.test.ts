/**
 * End-to-end verification against a REAL RabbitMQ broker. Skipped unless
 * RABBITMQ_TEST_URL is set, so it never breaks CI on a machine without a broker.
 *
 *   docker compose up -d rabbitmq
 *   RABBITMQ_TEST_URL=amqp://guest:guest@localhost:5672 bun test tests/integration/broker.test.ts
 *
 * It exercises the true topology: transient failures traverse the retry queue
 * and land in the DLQ once the attempt budget is spent, while valid messages
 * are delivered and acknowledged.
 */
import { afterAll, beforeAll, describe, expect, it } from 'bun:test';
import { Connection } from 'rabbitmq-client';
import { TransientDeliveryError } from '../../src/application/errors';
import { SendNotificationUseCase } from '../../src/application/send-notification';
import type { TopologyConfig } from '../../src/infrastructure/config/config';
import {
  createNotificationConsumer,
  type NotificationConsumer,
} from '../../src/infrastructure/messaging/consumer';
import { declareTopology } from '../../src/infrastructure/messaging/topology';
import { MetricsRegistry } from '../../src/infrastructure/observability/metrics';
import { createSilentLogger, StubSender } from '../support/fakes';

const TEST_URL = process.env.RABBITMQ_TEST_URL;
const suite = TEST_URL ? describe : describe.skip;

const topology: TopologyConfig = {
  exchange: 'test.notifications',
  queue: 'test.notifications',
  routingKey: 'notify',
  retryExchange: 'test.notifications.retry',
  retryQueue: 'test.notifications.retry',
  dlx: 'test.notifications.dlx',
  dlq: 'test.notifications.dlq',
  retryDelayMs: 500,
};

suite('broker integration (requires RABBITMQ_TEST_URL)', () => {
  let connection: Connection;
  let handles: NotificationConsumer;
  let sender: StubSender;

  beforeAll(async () => {
    connection = new Connection({ url: TEST_URL!, connectionName: 'notifications-test' });
    await connection.onConnect(10_000);
    await cleanup(connection);
    await declareTopology(connection, topology);

    // Messages whose text starts with "fail" throw a transient error forever.
    sender = new StubSender((n) => {
      if (n.text.startsWith('fail')) throw new TransientDeliveryError('forced failure');
    });
    const useCase = new SendNotificationUseCase({
      sender,
      logger: createSilentLogger(),
      maxAttempts: 2,
    });
    handles = createNotificationConsumer({
      connection,
      useCase,
      metrics: new MetricsRegistry(),
      logger: createSilentLogger(),
      config: {
        topology,
        rabbit: { url: TEST_URL!, prefetch: 5, concurrency: 2 },
        policy: { maxAttempts: 2 },
      },
    });
    await Bun.sleep(1500); // allow the consumer to become ready
  });

  afterAll(async () => {
    await handles?.consumer.close();
    await handles?.publisher.close();
    await cleanup(connection);
    await connection.close();
  });

  it('delivers a valid message and acknowledges it', async () => {
    const text = `ok-${Date.now()}`;
    await publish(connection, text);

    const delivered = await waitFor(() => sender.sent.some((n) => n.text === text), 6000);
    expect(delivered).toBe(true);
  });

  it('routes an always-failing message to the DLQ after exhausting retries', async () => {
    const text = `fail-${Date.now()}`;
    await publish(connection, text);

    const dead = await getFromDlq(connection, text, 8000);
    expect(dead).toBeDefined();
    expect(dead?.body?.text).toBe(text);
    expect(dead?.headers?.['x-dead-letter-category']).toBe('exhausted');
  });
});

async function publish(connection: Connection, text: string): Promise<void> {
  const publisher = connection.createPublisher({
    confirm: true,
    exchanges: [{ exchange: topology.exchange, type: 'direct', durable: true }],
  });
  await publisher.send(
    { exchange: topology.exchange, routingKey: topology.routingKey, durable: true },
    { text },
  );
  await publisher.close();
}

async function getFromDlq(connection: Connection, text: string, timeoutMs: number) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const msg = await connection.basicGet({ queue: topology.dlq, noAck: true });
    if (msg && msg.body?.text === text) return msg;
    if (!msg) await Bun.sleep(200);
  }
  return undefined;
}

async function waitFor(predicate: () => boolean, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return true;
    await Bun.sleep(100);
  }
  return predicate();
}

async function cleanup(connection: Connection): Promise<void> {
  for (const queue of [topology.queue, topology.retryQueue, topology.dlq]) {
    try {
      await connection.queueDelete({ queue });
    } catch {
      /* ignore */
    }
  }
  for (const exchange of [topology.exchange, topology.retryExchange, topology.dlx]) {
    try {
      await connection.exchangeDelete({ exchange });
    } catch {
      /* ignore */
    }
  }
}
