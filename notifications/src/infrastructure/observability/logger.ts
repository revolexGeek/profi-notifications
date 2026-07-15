import type { LogFields, Logger, LogLevel } from '../../application/ports';

const LEVEL_WEIGHT: Record<LogLevel, number> = { debug: 10, info: 20, warn: 30, error: 40 };

export interface LoggerOptions {
  readonly level?: LogLevel;
  readonly name?: string;
  /** Sink for one serialized JSON line. Defaults to console (stdout/stderr). */
  readonly sink?: (level: LogLevel, line: string) => void;
  /** Clock used for the `time` field; injectable for deterministic tests. */
  readonly now?: () => string;
}

/**
 * A dependency-free structured JSON logger. Emits one JSON object per line,
 * which plays well with log collectors (Loki, ELK, CloudWatch, …).
 */
export function createLogger(options: LoggerOptions = {}): Logger {
  const threshold = LEVEL_WEIGHT[options.level ?? 'info'];
  const service = options.name ?? 'notifications';
  const now = options.now ?? ((): string => new Date().toISOString());
  const sink = options.sink ?? defaultSink;

  const log = (level: LogLevel, message: string, fields?: LogFields): void => {
    if (LEVEL_WEIGHT[level] < threshold) return;
    const record = { level, time: now(), service, message, ...fields };
    sink(level, JSON.stringify(record));
  };

  return {
    debug: (message, fields) => log('debug', message, fields),
    info: (message, fields) => log('info', message, fields),
    warn: (message, fields) => log('warn', message, fields),
    error: (message, fields) => log('error', message, fields),
  };
}

function defaultSink(level: LogLevel, line: string): void {
  if (level === 'error' || level === 'warn') {
    console.error(line);
  } else {
    console.log(line);
  }
}
