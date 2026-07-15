import { describe, expect, it } from 'bun:test';
import { PermanentDeliveryError, TransientDeliveryError } from './errors';
import { SendNotificationUseCase } from './send-notification';
import { createRecordingLogger, createSilentLogger, StubSender } from '../../tests/support/fakes';

const MAX_ATTEMPTS = 5;

function makeUseCase(sender: StubSender, logger = createSilentLogger()): SendNotificationUseCase {
  return new SendNotificationUseCase({ sender, logger, maxAttempts: MAX_ATTEMPTS });
}

describe('SendNotificationUseCase', () => {
  it('acknowledges after a successful send', async () => {
    const sender = new StubSender();
    const useCase = makeUseCase(sender);

    const decision = await useCase.execute({ text: 'hi' }, { attempt: 0 });

    expect(decision).toEqual({ type: 'ack' });
    expect(sender.sent).toHaveLength(1);
    expect(sender.sent[0]?.text).toBe('hi');
  });

  it('dead-letters a domain-invalid command without calling the sender', async () => {
    const sender = new StubSender();
    const useCase = makeUseCase(sender);

    const decision = await useCase.execute({ text: '   ' }, { attempt: 0 });

    expect(decision).toEqual({
      type: 'dead-letter',
      category: 'validation',
      reason: expect.any(String),
    });
    expect(sender.sent).toHaveLength(0);
  });

  it('dead-letters immediately on a permanent transport error', async () => {
    const sender = new StubSender(() => {
      throw new PermanentDeliveryError('403 forbidden');
    });
    const useCase = makeUseCase(sender);

    const decision = await useCase.execute({ text: 'hi' }, { attempt: 0 });

    expect(decision).toEqual({
      type: 'dead-letter',
      category: 'permanent',
      reason: expect.stringContaining('403 forbidden'),
    });
  });

  it('retries on a transient error while attempts remain', async () => {
    const sender = new StubSender(() => {
      throw new TransientDeliveryError('503 unavailable');
    });
    const useCase = makeUseCase(sender);

    const decision = await useCase.execute({ text: 'hi' }, { attempt: 0 });

    expect(decision).toEqual({ type: 'retry' });
  });

  it('retries on the last attempt before the budget is spent', async () => {
    const sender = new StubSender(() => {
      throw new TransientDeliveryError('timeout');
    });
    const useCase = makeUseCase(sender);

    // attempt=3 means 3 prior failures; this makes the 4th, still < 5.
    const decision = await useCase.execute({ text: 'hi' }, { attempt: 3 });

    expect(decision).toEqual({ type: 'retry' });
  });

  it('dead-letters once transient retries are exhausted', async () => {
    const sender = new StubSender(() => {
      throw new TransientDeliveryError('still failing');
    });
    const useCase = makeUseCase(sender);

    // attempt=4 means 4 prior failures; this makes the 5th == maxAttempts.
    const decision = await useCase.execute({ text: 'hi' }, { attempt: 4 });

    expect(decision).toEqual({
      type: 'dead-letter',
      category: 'exhausted',
      reason: expect.stringContaining('exhausted'),
    });
  });

  it('treats an unknown error as transient and retries while attempts remain', async () => {
    const sender = new StubSender(() => {
      throw new Error('boom');
    });
    const useCase = makeUseCase(sender);

    const decision = await useCase.execute({ text: 'hi' }, { attempt: 0 });

    expect(decision).toEqual({ type: 'retry' });
  });

  it('dead-letters an unknown error as "unexpected" once exhausted', async () => {
    const sender = new StubSender(() => {
      throw new Error('boom');
    });
    const useCase = makeUseCase(sender);

    const decision = await useCase.execute({ text: 'hi' }, { attempt: 4 });

    expect(decision).toEqual({
      type: 'dead-letter',
      category: 'unexpected',
      reason: expect.any(String),
    });
  });

  it('logs a warning with the attempt number when retrying', async () => {
    const logger = createRecordingLogger();
    const sender = new StubSender(() => {
      throw new TransientDeliveryError('nope');
    });
    const useCase = makeUseCase(sender, logger);

    await useCase.execute({ text: 'hi' }, { attempt: 1 });

    const warning = logger.records.find((r) => r.level === 'warn');
    expect(warning?.fields).toMatchObject({ attempt: 2 });
  });
});
