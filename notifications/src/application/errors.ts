/**
 * Errors that a {@link NotificationSender} may raise. They classify a failure
 * as either retryable (transient) or terminal (permanent). The use case reacts
 * to these types, so the transport adapter is responsible for mapping its own
 * failures (HTTP status codes, network errors, …) onto them.
 */

/** A failure that may succeed if retried later (network blip, 5xx, 429, …). */
export class TransientDeliveryError extends Error {
  /** Suggested minimum delay before the next attempt, if the transport knows it. */
  readonly retryAfterMs?: number;

  constructor(message: string, options?: { retryAfterMs?: number; cause?: unknown }) {
    super(message, options?.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = 'TransientDeliveryError';
    if (options?.retryAfterMs !== undefined) {
      this.retryAfterMs = options.retryAfterMs;
    }
  }
}

/** A failure that will never succeed on retry (bad request, forbidden, …). */
export class PermanentDeliveryError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options?.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = 'PermanentDeliveryError';
  }
}
