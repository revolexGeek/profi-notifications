/**
 * Domain entity: a validated notification ready to be delivered to a channel.
 *
 * This module is the innermost circle — it depends on nothing outside itself
 * (no zod, no rabbitmq, no fetch). It encapsulates the enterprise rules that
 * define what a "sendable message" is, independent of any transport.
 */

/** Telegram text formatting modes. */
export const PARSE_MODES = ['HTML', 'MarkdownV2', 'Markdown'] as const;
export type ParseMode = (typeof PARSE_MODES)[number];

/**
 * Maximum length of a text message, in UTF-16 code units. This is an
 * enterprise rule of the messaging domain: a longer message simply cannot be
 * delivered, so it is invalid regardless of transport.
 */
export const MAX_TEXT_LENGTH = 4096;

/** Raw, not-yet-validated request to send a notification (a Request Model). */
export interface NotificationCommand {
  readonly text: string;
  readonly parseMode?: ParseMode;
  readonly disableNotification?: boolean;
  readonly disableWebPagePreview?: boolean;
  /** Target forum topic (message_thread_id). Overrides the configured default. */
  readonly messageThreadId?: number;
}

/** A validated notification. Existence of this type implies its invariants hold. */
export interface Notification {
  readonly text: string;
  readonly parseMode?: ParseMode;
  readonly disableNotification?: boolean;
  readonly disableWebPagePreview?: boolean;
  /** Target forum topic (message_thread_id). Overrides the configured default. */
  readonly messageThreadId?: number;
}

/** Thrown when a command violates a domain invariant. Always a permanent error. */
export class NotificationValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NotificationValidationError';
  }
}

/**
 * Construct a {@link Notification} from a command, enforcing domain invariants.
 * @throws {NotificationValidationError} when the text is empty or too long.
 */
export function createNotification(command: NotificationCommand): Notification {
  const { text } = command;

  if (typeof text !== 'string' || text.trim().length === 0) {
    throw new NotificationValidationError('text must be a non-empty string');
  }
  if (text.length > MAX_TEXT_LENGTH) {
    throw new NotificationValidationError(
      `text length ${text.length} exceeds the maximum of ${MAX_TEXT_LENGTH}`,
    );
  }
  if (
    command.messageThreadId !== undefined &&
    (!Number.isInteger(command.messageThreadId) || command.messageThreadId <= 0)
  ) {
    throw new NotificationValidationError('messageThreadId must be a positive integer');
  }

  return {
    text,
    ...(command.parseMode !== undefined ? { parseMode: command.parseMode } : {}),
    ...(command.disableNotification !== undefined
      ? { disableNotification: command.disableNotification }
      : {}),
    ...(command.disableWebPagePreview !== undefined
      ? { disableWebPagePreview: command.disableWebPagePreview }
      : {}),
    ...(command.messageThreadId !== undefined
      ? { messageThreadId: command.messageThreadId }
      : {}),
  };
}
