/**
 * Derives the retry attempt count from RabbitMQ's `x-death` header.
 *
 * When the main queue rejects a message (BasicNack requeue=false) it is
 * dead-lettered to the retry exchange with an `x-death` entry recording the
 * event. RabbitMQ increments that entry's `count` each time the message is
 * rejected at the same queue, so the count equals the number of *previous*
 * failed delivery attempts. A first delivery carries no `x-death` header.
 *
 * @see https://www.rabbitmq.com/dlx.html#effects
 */

interface XDeathEntry {
  count?: unknown;
  reason?: unknown;
  queue?: unknown;
}

export function getAttemptCount(
  headers: Record<string, unknown> | undefined,
  mainQueue: string,
): number {
  if (!headers) return 0;

  const xDeath = headers['x-death'];
  if (!Array.isArray(xDeath)) return 0;

  for (const entry of xDeath as XDeathEntry[]) {
    if (entry && entry.queue === mainQueue && entry.reason === 'rejected') {
      const count = Number(entry.count);
      return Number.isFinite(count) && count > 0 ? Math.floor(count) : 0;
    }
  }
  return 0;
}
