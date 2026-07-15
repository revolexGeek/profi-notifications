import type { Notification } from '../domain/notification';

/**
 * Output port: delivers a validated notification to some external channel.
 * Implemented in the infrastructure layer (e.g. the Telegram HTTP adapter).
 * On failure it must throw a `TransientDeliveryError` or `PermanentDeliveryError`
 * (see `./errors`) so the use case can decide whether to retry.
 */
export interface NotificationSender {
  send(notification: Notification): Promise<void>;
}

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';
export type LogFields = Record<string, unknown>;

/** Output port for structured logging. */
export interface Logger {
  debug(message: string, fields?: LogFields): void;
  info(message: string, fields?: LogFields): void;
  warn(message: string, fields?: LogFields): void;
  error(message: string, fields?: LogFields): void;
}
