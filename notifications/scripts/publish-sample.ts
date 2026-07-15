/**
 * Publishes one sample notification to the service's exchange — a quick way to
 * exercise the full pipeline locally.
 *
 *   bun run scripts/publish-sample.ts "Your message text"
 *
 * Reads only the RabbitMQ-related variables (no Telegram credentials needed).
 */
import { Connection } from 'rabbitmq-client';

const url = process.env.RABBITMQ_URL ?? 'amqp://guest:guest@localhost:5672';
const exchange = process.env.NOTIFY_EXCHANGE ?? 'notifications';
const routingKey = process.env.NOTIFY_ROUTING_KEY ?? 'notify';

const text = process.argv.slice(2).join(' ') || 'Hello from the notifications service ✅';

const rabbit = new Connection({ url, connectionName: 'notifications-sample-publisher' });
rabbit.on('error', (err) => console.error('connection error:', err));

await rabbit.onConnect(10_000);

const publisher = rabbit.createPublisher({
  confirm: true,
  maxAttempts: 3,
  exchanges: [{ exchange, type: 'direct', durable: true }],
});

await publisher.send({ exchange, routingKey, durable: true }, { text });
console.log(`published to exchange="${exchange}" routingKey="${routingKey}": ${text}`);

await publisher.close();
await rabbit.close();
