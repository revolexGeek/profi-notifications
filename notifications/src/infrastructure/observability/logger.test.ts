import { describe, expect, it, spyOn } from 'bun:test';
import type { LogLevel } from '../../application/ports';
import { createLogger } from './logger';

interface Captured {
  level: LogLevel;
  line: string;
}

function collectingLogger(level: LogLevel) {
  const lines: Captured[] = [];
  const logger = createLogger({
    level,
    name: 'test-svc',
    now: () => '2026-07-15T00:00:00.000Z',
    sink: (lvl, line) => lines.push({ level: lvl, line }),
  });
  return { logger, lines };
}

describe('createLogger', () => {
  it('emits a single JSON line with standard fields', () => {
    const { logger, lines } = collectingLogger('debug');

    logger.info('hello', { requestId: 'abc' });

    expect(lines).toHaveLength(1);
    const record = JSON.parse(lines[0]!.line);
    expect(record).toEqual({
      level: 'info',
      time: '2026-07-15T00:00:00.000Z',
      service: 'test-svc',
      message: 'hello',
      requestId: 'abc',
    });
  });

  it('suppresses messages below the configured level', () => {
    const { logger, lines } = collectingLogger('warn');

    logger.debug('nope');
    logger.info('nope');
    logger.warn('yes');
    logger.error('yes');

    expect(lines.map((l) => l.level)).toEqual(['warn', 'error']);
  });

  it('routes warn and error to the error stream signal', () => {
    const { logger, lines } = collectingLogger('debug');

    logger.error('boom');

    expect(lines[0]!.level).toBe('error');
  });

  it('works without any fields', () => {
    const { logger, lines } = collectingLogger('debug');

    logger.info('bare');

    const record = JSON.parse(lines[0]!.line);
    expect(record.message).toBe('bare');
  });
});

describe('createLogger default sink', () => {
  it('writes info/debug to stdout (console.log)', () => {
    const log = spyOn(console, 'log').mockImplementation(() => {});
    const err = spyOn(console, 'error').mockImplementation(() => {});
    try {
      const logger = createLogger({ level: 'debug', now: () => 'T' });
      logger.info('to stdout');

      expect(log).toHaveBeenCalledTimes(1);
      expect(err).not.toHaveBeenCalled();
    } finally {
      log.mockRestore();
      err.mockRestore();
    }
  });

  it('writes warn/error to stderr (console.error)', () => {
    const log = spyOn(console, 'log').mockImplementation(() => {});
    const err = spyOn(console, 'error').mockImplementation(() => {});
    try {
      const logger = createLogger({ level: 'debug', now: () => 'T' });
      logger.warn('warned');
      logger.error('failed');

      expect(err).toHaveBeenCalledTimes(2);
    } finally {
      log.mockRestore();
      err.mockRestore();
    }
  });
});
