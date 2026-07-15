import { describe, expect, it } from 'bun:test';
import type { Connection } from 'rabbitmq-client';
import type { TopologyConfig } from '../config/config';
import { declareTopology } from './topology';

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

function fakeConnection() {
  const exchanges: Array<Record<string, unknown>> = [];
  const queues: Array<Record<string, unknown>> = [];
  const binds: Array<Record<string, unknown>> = [];
  const connection = {
    exchangeDeclare: async (p: Record<string, unknown>) => {
      exchanges.push(p);
    },
    queueDeclare: async (p: Record<string, unknown>) => {
      queues.push(p);
      return { queue: String(p.queue), messageCount: 0, consumerCount: 0 };
    },
    queueBind: async (p: Record<string, unknown>) => {
      binds.push(p);
    },
  };
  return { connection: connection as unknown as Connection, exchanges, queues, binds };
}

describe('declareTopology', () => {
  it('declares three durable direct exchanges', async () => {
    const fake = fakeConnection();

    await declareTopology(fake.connection, topology);

    expect(fake.exchanges).toEqual([
      { exchange: 'notifications', type: 'direct', durable: true },
      { exchange: 'notifications.retry', type: 'direct', durable: true },
      { exchange: 'notifications.dlx', type: 'direct', durable: true },
    ]);
  });

  it('declares the main queue dead-lettering to the retry exchange', async () => {
    const fake = fakeConnection();

    await declareTopology(fake.connection, topology);

    expect(fake.queues).toContainEqual({
      queue: 'notifications',
      durable: true,
      arguments: {
        'x-dead-letter-exchange': 'notifications.retry',
        'x-dead-letter-routing-key': 'notify',
      },
    });
  });

  it('declares the retry queue with a TTL that dead-letters back to the main exchange', async () => {
    const fake = fakeConnection();

    await declareTopology(fake.connection, topology);

    expect(fake.queues).toContainEqual({
      queue: 'notifications.retry',
      durable: true,
      arguments: {
        'x-message-ttl': 30_000,
        'x-dead-letter-exchange': 'notifications',
        'x-dead-letter-routing-key': 'notify',
      },
    });
  });

  it('declares the dead-letter queue', async () => {
    const fake = fakeConnection();

    await declareTopology(fake.connection, topology);

    expect(fake.queues).toContainEqual({ queue: 'notifications.dlq', durable: true });
  });

  it('binds each queue to its exchange with the routing key', async () => {
    const fake = fakeConnection();

    await declareTopology(fake.connection, topology);

    expect(fake.binds).toEqual([
      { queue: 'notifications', exchange: 'notifications', routingKey: 'notify' },
      { queue: 'notifications.retry', exchange: 'notifications.retry', routingKey: 'notify' },
      { queue: 'notifications.dlq', exchange: 'notifications.dlx', routingKey: 'notify' },
    ]);
  });
});
