import { Connection } from 'rabbitmq-client';
import { SendNotificationUseCase } from './application/send-notification';
import { loadConfig } from './infrastructure/config/config';
import { createNotificationConsumer } from './infrastructure/messaging/consumer';
import { declareTopology } from './infrastructure/messaging/topology';
import { startHealthServer } from './infrastructure/http/server';
import { createLogger } from './infrastructure/observability/logger';
import { MetricsRegistry } from './infrastructure/observability/metrics';
import { TelegramNotificationSender } from './infrastructure/telegram/telegram-sender';

/**
 * Composition root. Nothing else in the codebase constructs concrete
 * implementations — this is the single place where the wiring happens, keeping
 * the inner circles free of framework and I/O dependencies.
 */
async function main(): Promise<void> {
  const config = loadConfig();
  const logger = createLogger({ level: config.logLevel, name: 'notifications' });
  const metrics = new MetricsRegistry();

  logger.info('starting notifications service', {
    queue: config.topology.queue,
    retryQueue: config.topology.retryQueue,
    dlq: config.topology.dlq,
    maxAttempts: config.policy.maxAttempts,
    retryDelayMs: config.topology.retryDelayMs,
    httpPort: config.http.port,
  });

  const sender = new TelegramNotificationSender({
    botToken: config.telegram.botToken,
    chatId: config.telegram.chatId,
    baseUrl: config.telegram.baseUrl,
    timeoutMs: config.telegram.timeoutMs,
    messageThreadId: config.telegram.messageThreadId,
  });

  const useCase = new SendNotificationUseCase({
    sender,
    logger,
    maxAttempts: config.policy.maxAttempts,
  });

  const connection = new Connection({
    url: config.rabbit.url,
    connectionName: 'notifications',
  });

  connection.on('error', (err: unknown) => {
    logger.error('rabbitmq connection error', {
      reason: err instanceof Error ? err.message : String(err),
    });
  });
  connection.on('connection', () => {
    logger.info('rabbitmq connected');
    // Re-assert the topology after every (re)connect. Idempotent.
    declareTopology(connection, config.topology).catch((err: unknown) => {
      logger.error('failed to declare topology', {
        reason: err instanceof Error ? err.message : String(err),
      });
    });
  });

  // Ensure we are connected and the topology exists before we start consuming.
  await connection.onConnect(15_000);
  await declareTopology(connection, config.topology);

  const { consumer, publisher } = createNotificationConsumer({
    connection,
    useCase,
    metrics,
    logger,
    config: {
      topology: config.topology,
      rabbit: config.rabbit,
      policy: config.policy,
    },
  });

  let consuming = false;
  consumer.on('ready', () => {
    consuming = true;
    logger.info('consumer ready');
  });

  const server = startHealthServer({
    host: config.http.host,
    port: config.http.port,
    logger,
    isLive: () => true,
    isReady: () => connection.ready && consuming,
    renderMetrics: () => metrics.render(),
  });

  let shuttingDown = false;
  const shutdown = async (signal: string): Promise<void> => {
    if (shuttingDown) return;
    shuttingDown = true;
    logger.info('shutting down', { signal });
    try {
      // Stop consuming first (waits for in-flight handlers), then tear down.
      await consumer.close();
      await publisher.close();
      await connection.close();
      await server.stop(true);
      logger.info('shutdown complete');
      process.exit(0);
    } catch (err) {
      logger.error('error during shutdown', {
        reason: err instanceof Error ? err.message : String(err),
      });
      process.exit(1);
    }
  };

  process.on('SIGTERM', () => void shutdown('SIGTERM'));
  process.on('SIGINT', () => void shutdown('SIGINT'));
}

main().catch((err: unknown) => {
  // Startup failed before the logger/service was ready — emit a raw JSON line.
  const reason = err instanceof Error ? (err.stack ?? err.message) : String(err);
  console.error(JSON.stringify({ level: 'error', service: 'notifications', message: 'fatal startup error', reason }));
  process.exit(1);
});
