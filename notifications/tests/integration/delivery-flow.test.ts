import { describe, expect, it } from 'bun:test';
import { ConsumerStatus } from 'rabbitmq-client';
import { PermanentDeliveryError, TransientDeliveryError } from '../../src/application/errors';
import { SendNotificationUseCase } from '../../src/application/send-notification';
import {
  createMessageHandler,
  type DeadLetterPublisher,
  type MessageLike,
} from '../../src/infrastructure/messaging/consumer';
import { MetricsRegistry } from '../../src/infrastructure/observability/metrics';
import type { Notification } from '../../src/domain/notification';
import { createSilentLogger, StubSender } from '../support/fakes';

const MAIN_QUEUE = 'notifications';
const MAX_ATTEMPTS = 5;

interface Dlq {
  body: unknown;
  reason: string;
  category: string;
}

function wire(behavior: (n: Notification) => void | Promise<void> = () => {}) {
  const sender = new StubSender(behavior);
  const logger = createSilentLogger();
  const metrics = new MetricsRegistry();
  const dlq: Dlq[] = [];
  const deadLetterPublisher: DeadLetterPublisher = {
    async publish({ body, reason, category }) {
      dlq.push({ body, reason, category });
    },
  };
  const useCase = new SendNotificationUseCase({ sender, logger, maxAttempts: MAX_ATTEMPTS });
  const handle = createMessageHandler({
    useCase,
    deadLetterPublisher,
    metrics,
    logger,
    mainQueue: MAIN_QUEUE,
    routingKey: 'notify',
    maxAttempts: MAX_ATTEMPTS,
  });
  return { sender, metrics, dlq, handle };
}

/** Simulate a message that the broker has already retried `attempt` times. */
function message(body: unknown, attempt = 0): MessageLike {
  if (attempt <= 0) return { body };
  return {
    body,
    headers: { 'x-death': [{ queue: MAIN_QUEUE, reason: 'rejected', count: attempt }] },
  };
}

describe('delivery flow (application + messaging integration)', () => {
  it('delivers a valid message and acknowledges it', async () => {
    const { sender, metrics, dlq, handle } = wire();

    const status = await handle(message({ text: 'hello', parseMode: 'HTML' }));

    expect(status).toBe(ConsumerStatus.ACK);
    expect(sender.sent).toEqual([{ text: 'hello', parseMode: 'HTML' }]);
    expect(dlq).toHaveLength(0);
    expect(metrics.snapshot()).toMatchObject({ received: 1, delivered: 1 });
  });

  it('dead-letters a structurally invalid payload without sending', async () => {
    const { sender, dlq, handle } = wire();

    const status = await handle(message({ notText: true }));

    expect(status).toBe(ConsumerStatus.ACK);
    expect(sender.sent).toHaveLength(0);
    expect(dlq[0]?.category).toBe('invalid-payload');
  });

  it('dead-letters a domain-invalid payload (empty text) without sending', async () => {
    const { sender, dlq, handle } = wire();

    const status = await handle(message({ text: '   ' }));

    expect(status).toBe(ConsumerStatus.ACK);
    expect(sender.sent).toHaveLength(0);
    expect(dlq[0]?.category).toBe('validation');
  });

  it('dead-letters immediately on a permanent transport failure', async () => {
    const { dlq, handle } = wire(() => {
      throw new PermanentDeliveryError('403 blocked');
    });

    const status = await handle(message({ text: 'hi' }));

    expect(status).toBe(ConsumerStatus.ACK);
    expect(dlq[0]?.category).toBe('permanent');
  });

  it('retries a transient failure, then dead-letters once the budget is spent', async () => {
    const { metrics, dlq, handle } = wire(() => {
      throw new TransientDeliveryError('503');
    });

    // Attempts 0..3 (the 1st..4th deliveries) should each be retried.
    for (let attempt = 0; attempt < MAX_ATTEMPTS - 1; attempt++) {
      const status = await handle(message({ text: 'hi' }, attempt));
      expect(status).toBe(ConsumerStatus.DROP);
    }

    // Attempt 4 (the 5th delivery) exhausts the budget → dead-letter.
    const final = await handle(message({ text: 'hi' }, MAX_ATTEMPTS - 1));
    expect(final).toBe(ConsumerStatus.ACK);
    expect(dlq).toHaveLength(1);
    expect(dlq[0]?.category).toBe('exhausted');
    expect(metrics.snapshot()).toMatchObject({ received: 5, retried: 4 });
  });

  it('recovers mid-retry: a transient failure that later succeeds is delivered', async () => {
    let attempts = 0;
    const { sender, dlq, handle } = wire(() => {
      attempts += 1;
      if (attempts === 1) throw new TransientDeliveryError('temporary');
    });

    const first = await handle(message({ text: 'hi' }, 0));
    expect(first).toBe(ConsumerStatus.DROP);

    const second = await handle(message({ text: 'hi' }, 1));
    expect(second).toBe(ConsumerStatus.ACK);
    expect(sender.sent).toHaveLength(2);
    expect(dlq).toHaveLength(0);
  });
});
