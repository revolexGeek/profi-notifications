import { describe, expect, it } from 'bun:test';
import { ConfigError, loadConfig } from './config';

const REQUIRED = {
  TELEGRAM_BOT_TOKEN: 'token',
  TELEGRAM_CHAT_ID: '@channel',
  RABBITMQ_URL: 'amqp://localhost',
};

describe('loadConfig', () => {
  it('applies defaults when only required vars are present', () => {
    const config = loadConfig(REQUIRED);

    expect(config.telegram.baseUrl).toBe('https://api.telegram.org');
    expect(config.telegram.timeoutMs).toBe(10_000);
    expect(config.rabbit.prefetch).toBe(10);
    expect(config.rabbit.concurrency).toBe(5);
    expect(config.topology.exchange).toBe('notifications');
    expect(config.topology.retryQueue).toBe('notifications.retry');
    expect(config.topology.dlq).toBe('notifications.dlq');
    expect(config.topology.retryDelayMs).toBe(30_000);
    expect(config.policy.maxAttempts).toBe(5);
    expect(config.http.port).toBe(3000);
    expect(config.logLevel).toBe('info');
  });

  it('carries required values through', () => {
    const config = loadConfig(REQUIRED);

    expect(config.telegram.botToken).toBe('token');
    expect(config.telegram.chatId).toBe('@channel');
    expect(config.rabbit.url).toBe('amqp://localhost');
  });

  it('coerces numeric env vars from strings', () => {
    const config = loadConfig({
      ...REQUIRED,
      NOTIFY_MAX_ATTEMPTS: '3',
      RABBITMQ_PREFETCH: '25',
      HTTP_PORT: '8080',
    });

    expect(config.policy.maxAttempts).toBe(3);
    expect(config.rabbit.prefetch).toBe(25);
    expect(config.http.port).toBe(8080);
  });

  it('throws when a required var is missing', () => {
    expect(() => loadConfig({ TELEGRAM_BOT_TOKEN: 't', TELEGRAM_CHAT_ID: 'c' })).toThrow(
      ConfigError,
    );
  });

  it('reports the offending field in the error message', () => {
    expect(() => loadConfig({ ...REQUIRED, TELEGRAM_BOT_TOKEN: '' })).toThrow(
      /TELEGRAM_BOT_TOKEN/,
    );
  });

  it('rejects a non-numeric numeric var', () => {
    expect(() => loadConfig({ ...REQUIRED, NOTIFY_MAX_ATTEMPTS: 'lots' })).toThrow(ConfigError);
  });

  it('rejects an invalid base url', () => {
    expect(() => loadConfig({ ...REQUIRED, TELEGRAM_API_BASE_URL: 'ftp://x' })).toThrow(
      ConfigError,
    );
  });

  it('rejects an out-of-range port', () => {
    expect(() => loadConfig({ ...REQUIRED, HTTP_PORT: '70000' })).toThrow(ConfigError);
  });

  it('rejects an unknown log level', () => {
    expect(() => loadConfig({ ...REQUIRED, LOG_LEVEL: 'verbose' })).toThrow(ConfigError);
  });
});
