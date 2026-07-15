import type { LogFields, Logger, LogLevel, NotificationSender } from '../../src/application/ports';
import type { Notification } from '../../src/domain/notification';

/** A logger that discards everything — for tests that don't assert on logs. */
export function createSilentLogger(): Logger {
  const noop = (): void => {};
  return { debug: noop, info: noop, warn: noop, error: noop };
}

export interface RecordedLog {
  readonly level: LogLevel;
  readonly message: string;
  readonly fields: LogFields | undefined;
}

/** A logger that records every call so tests can assert on emitted logs. */
export function createRecordingLogger(): Logger & { readonly records: RecordedLog[] } {
  const records: RecordedLog[] = [];
  const make =
    (level: LogLevel) =>
    (message: string, fields?: LogFields): void => {
      records.push({ level, message, fields });
    };
  return {
    records,
    debug: make('debug'),
    info: make('info'),
    warn: make('warn'),
    error: make('error'),
  };
}

/** A configurable {@link NotificationSender} test double. */
export class StubSender implements NotificationSender {
  readonly sent: Notification[] = [];
  private readonly behavior: (n: Notification) => void | Promise<void>;

  constructor(behavior: (n: Notification) => void | Promise<void> = () => {}) {
    this.behavior = behavior;
  }

  async send(notification: Notification): Promise<void> {
    this.sent.push(notification);
    await this.behavior(notification);
  }
}
