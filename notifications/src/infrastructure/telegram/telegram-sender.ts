import { PermanentDeliveryError, TransientDeliveryError } from '../../application/errors';
import type { NotificationSender } from '../../application/ports';
import type { Notification } from '../../domain/notification';

/** The subset of `fetch` we depend on — injectable so tests need no network. */
export type FetchLike = (input: string, init: RequestInit) => Promise<Response>;

export interface TelegramSenderOptions {
  readonly botToken: string;
  readonly chatId: string;
  readonly baseUrl?: string;
  readonly timeoutMs?: number;
  readonly fetch?: FetchLike;
}

interface TelegramResponseBody {
  ok?: boolean;
  error_code?: number;
  description?: string;
  parameters?: { retry_after?: number; migrate_to_chat_id?: number };
}

/**
 * Interface Adapter that turns a domain {@link Notification} into a Telegram
 * Bot API `sendMessage` call. All Telegram/HTTP specifics live here; the rest
 * of the system only sees the {@link NotificationSender} port and the
 * transient/permanent error taxonomy.
 */
export class TelegramNotificationSender implements NotificationSender {
  private readonly endpoint: string;
  private readonly chatId: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: FetchLike;

  constructor(options: TelegramSenderOptions) {
    const baseUrl = (options.baseUrl ?? 'https://api.telegram.org').replace(/\/+$/, '');
    this.endpoint = `${baseUrl}/bot${options.botToken}/sendMessage`;
    this.chatId = options.chatId;
    this.timeoutMs = options.timeoutMs ?? 10_000;
    this.fetchImpl = options.fetch ?? ((input, init) => fetch(input, init));
  }

  async send(notification: Notification): Promise<void> {
    const payload = this.buildPayload(notification);

    let response: Response;
    try {
      response = await this.fetchImpl(this.endpoint, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch (err) {
      // Network failure, DNS error, or timeout/abort — all retryable.
      throw new TransientDeliveryError(`telegram request failed: ${errorMessage(err)}`, {
        cause: err,
      });
    }

    const body = (await response.json().catch(() => null)) as TelegramResponseBody | null;

    if (response.ok && body?.ok !== false) {
      return;
    }

    throw classifyFailure(response.status, body);
  }

  private buildPayload(notification: Notification): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      chat_id: this.chatId,
      text: notification.text,
    };
    if (notification.parseMode !== undefined) {
      payload.parse_mode = notification.parseMode;
    }
    if (notification.disableNotification !== undefined) {
      payload.disable_notification = notification.disableNotification;
    }
    if (notification.disableWebPagePreview !== undefined) {
      payload.link_preview_options = { is_disabled: notification.disableWebPagePreview };
    }
    return payload;
  }
}

function classifyFailure(status: number, body: TelegramResponseBody | null): Error {
  const description = body?.description ?? `HTTP ${status}`;
  const retryAfterSec = body?.parameters?.retry_after;

  // 429 Too Many Requests — always transient; honor Telegram's retry hint.
  if (status === 429) {
    return new TransientDeliveryError(
      `telegram rate limited: ${description}`,
      retryAfterSec !== undefined ? { retryAfterMs: retryAfterSec * 1000 } : undefined,
    );
  }

  // 5xx — server side, retry later.
  if (status >= 500) {
    return new TransientDeliveryError(`telegram server error ${status}: ${description}`);
  }

  // 4xx (400 bad request, 401 bad token, 403 blocked, 404 chat gone, …) —
  // retrying won't help: the request or configuration is wrong.
  if (status >= 400) {
    return new PermanentDeliveryError(`telegram rejected message ${status}: ${description}`);
  }

  // 2xx with ok:false, or an unexpected 3xx — err on the side of retrying.
  return new TransientDeliveryError(`unexpected telegram response ${status}: ${description}`);
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
