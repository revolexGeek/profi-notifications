import { describe, expect, it } from 'bun:test';
import { getAttemptCount } from './retry';

const MAIN = 'notifications';

describe('getAttemptCount', () => {
  it('returns 0 when headers are undefined (first delivery)', () => {
    expect(getAttemptCount(undefined, MAIN)).toBe(0);
  });

  it('returns 0 when there is no x-death header', () => {
    expect(getAttemptCount({ 'some-header': 'x' }, MAIN)).toBe(0);
  });

  it('returns 0 when x-death is not an array', () => {
    expect(getAttemptCount({ 'x-death': 'nope' }, MAIN)).toBe(0);
  });

  it('reads the count from the matching rejected entry', () => {
    const headers = {
      'x-death': [
        { queue: MAIN, reason: 'rejected', count: 3 },
        { queue: 'notifications.retry', reason: 'expired', count: 3 },
      ],
    };

    expect(getAttemptCount(headers, MAIN)).toBe(3);
  });

  it('ignores entries for other queues', () => {
    const headers = {
      'x-death': [{ queue: 'other', reason: 'rejected', count: 9 }],
    };

    expect(getAttemptCount(headers, MAIN)).toBe(0);
  });

  it('ignores non-rejection reasons', () => {
    const headers = {
      'x-death': [{ queue: MAIN, reason: 'expired', count: 5 }],
    };

    expect(getAttemptCount(headers, MAIN)).toBe(0);
  });

  it('coerces a numeric-looking count value', () => {
    const headers = {
      'x-death': [{ queue: MAIN, reason: 'rejected', count: '2' }],
    };

    expect(getAttemptCount(headers, MAIN)).toBe(2);
  });

  it('treats a zero or malformed count as 0', () => {
    expect(getAttemptCount({ 'x-death': [{ queue: MAIN, reason: 'rejected', count: 0 }] }, MAIN)).toBe(
      0,
    );
    expect(
      getAttemptCount({ 'x-death': [{ queue: MAIN, reason: 'rejected', count: 'x' }] }, MAIN),
    ).toBe(0);
  });
});
