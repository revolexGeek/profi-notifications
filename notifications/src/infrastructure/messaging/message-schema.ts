import { z } from 'zod';
import { PARSE_MODES, type NotificationCommand } from '../../domain/notification';

/**
 * Structural contract for an incoming message. zod validates the shape and
 * types only; domain invariants (non-empty text, length limit) are enforced by
 * {@link import('../../domain/notification').createNotification}. Unknown keys
 * are stripped so producers can add fields without breaking this consumer.
 */
export const notificationMessageSchema = z.object({
  text: z.string(),
  parseMode: z.enum(PARSE_MODES).optional(),
  disableNotification: z.boolean().optional(),
  disableWebPagePreview: z.boolean().optional(),
});

export type ParseSuccess = { readonly ok: true; readonly command: NotificationCommand };
export type ParseFailure = { readonly ok: false; readonly reason: string };
export type ParseResult = ParseSuccess | ParseFailure;

/**
 * Parse a raw AMQP message body into a {@link NotificationCommand}. Accepts an
 * already-decoded object (rabbitmq-client auto-parses `application/json`) or a
 * string / Buffer containing JSON. Never throws — returns a tagged result.
 */
export function parseNotificationMessage(raw: unknown): ParseResult {
  const candidate = coerceToObject(raw);
  if (candidate === undefined) {
    return { ok: false, reason: 'message body is not a JSON object' };
  }

  const result = notificationMessageSchema.safeParse(candidate);
  if (!result.success) {
    const reason = result.error.issues
      .map((issue) => `${issue.path.join('.') || '(root)'}: ${issue.message}`)
      .join('; ');
    return { ok: false, reason };
  }

  return { ok: true, command: result.data };
}

function coerceToObject(raw: unknown): Record<string, unknown> | undefined {
  if (raw === null || raw === undefined) return undefined;

  if (isBytes(raw)) {
    return parseJsonObject(Buffer.from(raw as Uint8Array).toString('utf8'));
  }
  if (typeof raw === 'string') {
    return parseJsonObject(raw);
  }
  if (typeof raw === 'object') {
    return raw as Record<string, unknown>;
  }
  return undefined;
}

function parseJsonObject(text: string): Record<string, unknown> | undefined {
  try {
    const parsed: unknown = JSON.parse(text);
    return typeof parsed === 'object' && parsed !== null
      ? (parsed as Record<string, unknown>)
      : undefined;
  } catch {
    return undefined;
  }
}

function isBytes(value: unknown): boolean {
  return value instanceof Uint8Array || (typeof Buffer !== 'undefined' && Buffer.isBuffer(value));
}
