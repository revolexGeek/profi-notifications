import { describe, expect, it } from 'bun:test';
import { PermanentDeliveryError, TransientDeliveryError } from './errors';

describe('TransientDeliveryError', () => {
  it('carries the message and a stable name', () => {
    const err = new TransientDeliveryError('temporary');

    expect(err).toBeInstanceOf(Error);
    expect(err.message).toBe('temporary');
    expect(err.name).toBe('TransientDeliveryError');
    expect(err.retryAfterMs).toBeUndefined();
  });

  it('records retryAfterMs when provided', () => {
    const err = new TransientDeliveryError('rate limited', { retryAfterMs: 5000 });

    expect(err.retryAfterMs).toBe(5000);
  });

  it('preserves the underlying cause', () => {
    const cause = new Error('socket hang up');
    const err = new TransientDeliveryError('network', { cause });

    expect(err.cause).toBe(cause);
  });
});

describe('PermanentDeliveryError', () => {
  it('carries the message and a stable name', () => {
    const err = new PermanentDeliveryError('forbidden');

    expect(err).toBeInstanceOf(Error);
    expect(err.message).toBe('forbidden');
    expect(err.name).toBe('PermanentDeliveryError');
  });

  it('preserves the underlying cause', () => {
    const cause = new Error('bad request');
    const err = new PermanentDeliveryError('rejected', { cause });

    expect(err.cause).toBe(cause);
  });
});
