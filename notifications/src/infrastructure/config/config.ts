import { z } from 'zod';
import type { LogLevel } from '../../application/ports';

/**
 * Environment schema. zod lives at the edge of the system (infrastructure),
 * converting the untyped process environment into a validated, typed config.
 */
const EnvSchema = z.object({
  TELEGRAM_BOT_TOKEN: z.string().min(1, 'TELEGRAM_BOT_TOKEN is required'),
  TELEGRAM_CHAT_ID: z.string().min(1, 'TELEGRAM_CHAT_ID is required'),
  TELEGRAM_API_BASE_URL: z
    .string()
    .regex(/^https?:\/\//, 'must start with http:// or https://')
    .default('https://api.telegram.org'),
  TELEGRAM_TIMEOUT_MS: z.coerce.number().int().positive().default(10_000),

  RABBITMQ_URL: z.string().min(1, 'RABBITMQ_URL is required'),
  RABBITMQ_PREFETCH: z.coerce.number().int().positive().default(10),
  RABBITMQ_CONCURRENCY: z.coerce.number().int().positive().default(5),

  NOTIFY_EXCHANGE: z.string().min(1).default('notifications'),
  NOTIFY_QUEUE: z.string().min(1).default('notifications'),
  NOTIFY_ROUTING_KEY: z.string().min(1).default('notify'),
  NOTIFY_RETRY_EXCHANGE: z.string().min(1).default('notifications.retry'),
  NOTIFY_RETRY_QUEUE: z.string().min(1).default('notifications.retry'),
  NOTIFY_DLX: z.string().min(1).default('notifications.dlx'),
  NOTIFY_DLQ: z.string().min(1).default('notifications.dlq'),

  NOTIFY_MAX_ATTEMPTS: z.coerce.number().int().positive().default(5),
  NOTIFY_RETRY_DELAY_MS: z.coerce.number().int().positive().default(30_000),

  HTTP_HOST: z.string().min(1).default('0.0.0.0'),
  HTTP_PORT: z.coerce.number().int().min(0).max(65_535).default(3000),

  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

export interface TelegramConfig {
  readonly botToken: string;
  readonly chatId: string;
  readonly baseUrl: string;
  readonly timeoutMs: number;
}

export interface RabbitConfig {
  readonly url: string;
  readonly prefetch: number;
  readonly concurrency: number;
}

export interface TopologyConfig {
  readonly exchange: string;
  readonly queue: string;
  readonly routingKey: string;
  readonly retryExchange: string;
  readonly retryQueue: string;
  readonly dlx: string;
  readonly dlq: string;
  readonly retryDelayMs: number;
}

export interface PolicyConfig {
  readonly maxAttempts: number;
}

export interface HttpConfig {
  readonly host: string;
  readonly port: number;
}

export interface AppConfig {
  readonly telegram: TelegramConfig;
  readonly rabbit: RabbitConfig;
  readonly topology: TopologyConfig;
  readonly policy: PolicyConfig;
  readonly http: HttpConfig;
  readonly logLevel: LogLevel;
}

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

/**
 * Parse and validate configuration from an environment map.
 * @throws {ConfigError} with a readable summary if anything is invalid.
 */
export function loadConfig(env: Record<string, string | undefined> = process.env): AppConfig {
  const result = EnvSchema.safeParse(env);
  if (!result.success) {
    const details = result.error.issues
      .map((issue) => `${issue.path.join('.') || '(root)'}: ${issue.message}`)
      .join('; ');
    throw new ConfigError(`Invalid configuration: ${details}`);
  }

  const e = result.data;
  return {
    telegram: {
      botToken: e.TELEGRAM_BOT_TOKEN,
      chatId: e.TELEGRAM_CHAT_ID,
      baseUrl: e.TELEGRAM_API_BASE_URL,
      timeoutMs: e.TELEGRAM_TIMEOUT_MS,
    },
    rabbit: {
      url: e.RABBITMQ_URL,
      prefetch: e.RABBITMQ_PREFETCH,
      concurrency: e.RABBITMQ_CONCURRENCY,
    },
    topology: {
      exchange: e.NOTIFY_EXCHANGE,
      queue: e.NOTIFY_QUEUE,
      routingKey: e.NOTIFY_ROUTING_KEY,
      retryExchange: e.NOTIFY_RETRY_EXCHANGE,
      retryQueue: e.NOTIFY_RETRY_QUEUE,
      dlx: e.NOTIFY_DLX,
      dlq: e.NOTIFY_DLQ,
      retryDelayMs: e.NOTIFY_RETRY_DELAY_MS,
    },
    policy: {
      maxAttempts: e.NOTIFY_MAX_ATTEMPTS,
    },
    http: {
      host: e.HTTP_HOST,
      port: e.HTTP_PORT,
    },
    logLevel: e.LOG_LEVEL,
  };
}
