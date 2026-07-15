import { describe, expect, it } from 'bun:test';
import { ConsumerStatus } from 'rabbitmq-client';
import type { DeliveryDecision } from '../../application/delivery-decision';
import type { SendContext } from '../../application/send-notification';
import type { NotificationCommand } from '../../domain/notification';
import { MetricsRegistry } from '../observability/metrics';
import { createSilentLogger } from '../../../tests/support/fakes';
import {
  createMessageHandler,
  type DeadLetterPublisher,
  type MessageHandlerDeps,
  type MessageLike,
} from './consumer';

interface PublishedDlq {
  routingKey: string;
  body: unknown;
  headers: Record<string, unknown>;
  reason: string;
  category: string;
}

function recordingDlqPublisher(sink: PublishedDlq[]): DeadLetterPublisher {
  return {
    async publish(input) {
      sink.push(input);
    },
  };
}

interface StubUseCase {
  execute(command: NotificationCommand, ctx: SendContext): Promise<DeliveryDecision>;
  readonly calls: Array<{ command: NotificationCommand; ctx: SendContext }>;
}

function stubUseCase(behavior: (ctx: SendContext) => DeliveryDecision): StubUseCase {
  const calls: StubUseCase['calls'] = [];
  return {
    calls,
    async execute(command, ctx) {
      calls.push({ command, ctx });
      return behavior(ctx);
    },
  };
}

function makeHandler(
  useCase: StubUseCase,
  overrides: Partial<MessageHandlerDeps> = {},
): {
  handle: (msg: MessageLike) => Promise<ConsumerStatus>;
  dlq: PublishedDlq[];
  metrics: MetricsRegistry;
} {
  const dlq: PublishedDlq[] = [];
  const metrics = new MetricsRegistry();
  const handle = createMessageHandler({
    useCase,
    deadLetterPublisher: recordingDlqPublisher(dlq),
    metrics,
    logger: createSilentLogger(),
    mainQueue: 'notifications',
    routingKey: 'notify',
    maxAttempts: 5,
    ...overrides,
  });
  return { handle, dlq, metrics };
}

describe('createMessageHandler', () => {
  it('acks a delivered message and records the metric', async () => {
    const useCase = stubUseCase(() => ({ type: 'ack' }));
    const { handle, dlq, metrics } = makeHandler(useCase);

    const status = await handle({ body: { text: 'hi' } });

    expect(status).toBe(ConsumerStatus.ACK);
    expect(dlq).toHaveLength(0);
    expect(metrics.snapshot()).toMatchObject({ received: 1, delivered: 1 });
  });

  it('drops (nacks to retry) on a retry decision', async () => {
    const useCase = stubUseCase(() => ({ type: 'retry' }));
    const { handle, dlq, metrics } = makeHandler(useCase);

    const status = await handle({ body: { text: 'hi' } });

    expect(status).toBe(ConsumerStatus.DROP);
    expect(dlq).toHaveLength(0);
    expect(metrics.snapshot()).toMatchObject({ received: 1, retried: 1 });
  });

  it('publishes to the DLQ and acks on a dead-letter decision', async () => {
    const useCase = stubUseCase(() => ({
      type: 'dead-letter',
      category: 'permanent',
      reason: 'nope',
    }));
    const { handle, dlq, metrics } = makeHandler(useCase);

    const status = await handle({
      body: { text: 'hi' },
      headers: { 'x-death': [] },
      routingKey: 'notify',
    });

    expect(status).toBe(ConsumerStatus.ACK);
    expect(dlq).toHaveLength(1);
    expect(dlq[0]).toMatchObject({
      routingKey: 'notify',
      body: { text: 'hi' },
      reason: 'nope',
      category: 'permanent',
    });
    expect(metrics.snapshot().deadLettered).toEqual({ permanent: 1 });
  });

  it('dead-letters an unparseable payload without invoking the use case', async () => {
    const useCase = stubUseCase(() => ({ type: 'ack' }));
    const { handle, dlq } = makeHandler(useCase);

    const status = await handle({ body: 'not json' });

    expect(status).toBe(ConsumerStatus.ACK);
    expect(useCase.calls).toHaveLength(0);
    expect(dlq[0]?.category).toBe('invalid-payload');
  });

  it('passes the x-death attempt count to the use case', async () => {
    const useCase = stubUseCase(() => ({ type: 'ack' }));
    const { handle } = makeHandler(useCase);

    await handle({
      body: { text: 'hi' },
      headers: { 'x-death': [{ queue: 'notifications', reason: 'rejected', count: 2 }] },
    });

    expect(useCase.calls[0]?.ctx).toEqual({ attempt: 2 });
  });

  it('retries when the use case throws and attempts remain', async () => {
    const useCase = stubUseCase(() => {
      throw new Error('kaboom');
    });
    const { handle, dlq } = makeHandler(useCase);

    const status = await handle({ body: { text: 'hi' } });

    expect(status).toBe(ConsumerStatus.DROP);
    expect(dlq).toHaveLength(0);
  });

  it('dead-letters as "unexpected" when the use case throws and attempts are spent', async () => {
    const useCase = stubUseCase(() => {
      throw new Error('kaboom');
    });
    const { handle, dlq } = makeHandler(useCase);

    const status = await handle({
      body: { text: 'hi' },
      headers: { 'x-death': [{ queue: 'notifications', reason: 'rejected', count: 4 }] },
    });

    expect(status).toBe(ConsumerStatus.ACK);
    expect(dlq[0]?.category).toBe('unexpected');
  });
});
