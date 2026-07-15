import {
  createNotification,
  NotificationValidationError,
  type Notification,
  type NotificationCommand,
} from '../domain/notification';
import {
  ackDecision,
  deadLetterDecision,
  retryDecision,
  type DeliveryDecision,
} from './delivery-decision';
import { PermanentDeliveryError, TransientDeliveryError } from './errors';
import type { Logger, NotificationSender } from './ports';

export interface SendContext {
  /** Number of previous failed delivery attempts (0 on the first delivery). */
  readonly attempt: number;
}

export interface SendNotificationDeps {
  readonly sender: NotificationSender;
  readonly logger: Logger;
  /** Total number of attempts allowed before a message is dead-lettered. */
  readonly maxAttempts: number;
}

/**
 * Application business rule: given a command, deliver it and decide what should
 * happen to the source message. This is the single place that owns the
 * "confirm only after a successful send, otherwise retry or dead-letter" policy.
 */
export class SendNotificationUseCase {
  constructor(private readonly deps: SendNotificationDeps) {}

  async execute(command: NotificationCommand, ctx: SendContext): Promise<DeliveryDecision> {
    let notification: Notification;
    try {
      notification = createNotification(command);
    } catch (err) {
      if (err instanceof NotificationValidationError) {
        this.deps.logger.warn('notification rejected: failed domain validation', {
          reason: err.message,
        });
        return deadLetterDecision('validation', err.message);
      }
      throw err;
    }

    try {
      await this.deps.sender.send(notification);
      this.deps.logger.debug('notification delivered');
      return ackDecision();
    } catch (err) {
      return this.onSendError(err, ctx);
    }
  }

  private onSendError(err: unknown, ctx: SendContext): DeliveryDecision {
    if (err instanceof PermanentDeliveryError) {
      this.deps.logger.error('notification permanently rejected by transport', {
        reason: err.message,
      });
      return deadLetterDecision('permanent', err.message);
    }

    const attemptsMade = ctx.attempt + 1;
    const exhausted = attemptsMade >= this.deps.maxAttempts;

    if (err instanceof TransientDeliveryError) {
      if (exhausted) {
        this.deps.logger.error('notification failed: retries exhausted', {
          attempts: attemptsMade,
          reason: err.message,
        });
        return deadLetterDecision(
          'exhausted',
          `retries exhausted after ${attemptsMade} attempt(s): ${err.message}`,
        );
      }
      this.deps.logger.warn('notification transiently failed; will retry', {
        attempt: attemptsMade,
        reason: err.message,
      });
      return retryDecision();
    }

    // Unknown error shape: be conservative and treat it as transient so we do
    // not silently drop a message, but still respect the attempt budget.
    const reason = err instanceof Error ? err.message : String(err);
    if (exhausted) {
      this.deps.logger.error('notification failed with unexpected error: retries exhausted', {
        attempts: attemptsMade,
        reason,
      });
      return deadLetterDecision('unexpected', `unexpected error, retries exhausted: ${reason}`);
    }
    this.deps.logger.error('notification failed with unexpected error; will retry', {
      attempt: attemptsMade,
      reason,
    });
    return retryDecision();
  }
}
