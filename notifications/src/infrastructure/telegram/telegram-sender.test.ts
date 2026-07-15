import { describe, expect, it, spyOn } from 'bun:test';
import { PermanentDeliveryError, TransientDeliveryError } from '../../application/errors';
import type { Notification } from '../../domain/notification';
import { TelegramNotificationSender, type FetchLike } from './telegram-sender';

interface CapturedRequest {
  url: string;
  init: RequestInit;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function makeSender(
  reply: () => Promise<Response> | Response,
  captured: CapturedRequest[] = [],
): TelegramNotificationSender {
  const fetchImpl: FetchLike = async (url, init) => {
    captured.push({ url, init });
    return reply();
  };
  return new TelegramNotificationSender({
    botToken: 'BOT123',
    chatId: '@channel',
    baseUrl: 'https://tg.test/',
    timeoutMs: 5000,
    fetch: fetchImpl,
  });
}

describe('TelegramNotificationSender', () => {
  it('resolves on a successful response', async () => {
    const sender = makeSender(() => jsonResponse({ ok: true, result: { message_id: 1 } }));

    await expect(sender.send({ text: 'hello' })).resolves.toBeUndefined();
  });

  it('builds the correct request URL, method and headers', async () => {
    const captured: CapturedRequest[] = [];
    const sender = makeSender(() => jsonResponse({ ok: true }), captured);

    await sender.send({ text: 'hello' });

    expect(captured).toHaveLength(1);
    expect(captured[0]!.url).toBe('https://tg.test/botBOT123/sendMessage');
    expect(captured[0]!.init.method).toBe('POST');
    expect(captured[0]!.init.headers).toMatchObject({ 'content-type': 'application/json' });
  });

  it('maps all notification fields into the Telegram payload', async () => {
    const captured: CapturedRequest[] = [];
    const sender = makeSender(() => jsonResponse({ ok: true }), captured);
    const notification: Notification = {
      text: 'body',
      parseMode: 'HTML',
      disableNotification: true,
      disableWebPagePreview: true,
    };

    await sender.send(notification);

    const payload = JSON.parse(String(captured[0]!.init.body));
    expect(payload).toEqual({
      chat_id: '@channel',
      text: 'body',
      parse_mode: 'HTML',
      disable_notification: true,
      link_preview_options: { is_disabled: true },
    });
  });

  it('omits optional fields that are not set', async () => {
    const captured: CapturedRequest[] = [];
    const sender = makeSender(() => jsonResponse({ ok: true }), captured);

    await sender.send({ text: 'plain' });

    const payload = JSON.parse(String(captured[0]!.init.body));
    expect(payload).toEqual({ chat_id: '@channel', text: 'plain' });
  });

  it('throws a permanent error on 400 Bad Request', async () => {
    const sender = makeSender(() =>
      jsonResponse({ ok: false, error_code: 400, description: 'Bad Request: message is empty' }, 400),
    );

    await expect(sender.send({ text: 'x' })).rejects.toBeInstanceOf(PermanentDeliveryError);
  });

  it('throws a permanent error on 403 Forbidden', async () => {
    const sender = makeSender(() =>
      jsonResponse({ ok: false, error_code: 403, description: 'Forbidden: bot was blocked' }, 403),
    );

    await expect(sender.send({ text: 'x' })).rejects.toBeInstanceOf(PermanentDeliveryError);
  });

  it('throws a permanent error on 401 Unauthorized', async () => {
    const sender = makeSender(() =>
      jsonResponse({ ok: false, error_code: 401, description: 'Unauthorized' }, 401),
    );

    await expect(sender.send({ text: 'x' })).rejects.toBeInstanceOf(PermanentDeliveryError);
  });

  it('throws a transient error on 429 and surfaces retry_after', async () => {
    const sender = makeSender(() =>
      jsonResponse(
        { ok: false, error_code: 429, description: 'Too Many Requests', parameters: { retry_after: 7 } },
        429,
      ),
    );

    try {
      await sender.send({ text: 'x' });
      throw new Error('expected send to reject');
    } catch (err) {
      expect(err).toBeInstanceOf(TransientDeliveryError);
      expect((err as TransientDeliveryError).retryAfterMs).toBe(7000);
    }
  });

  it('throws a transient error on 500', async () => {
    const sender = makeSender(() => jsonResponse({ ok: false, description: 'Internal' }, 500));

    await expect(sender.send({ text: 'x' })).rejects.toBeInstanceOf(TransientDeliveryError);
  });

  it('throws a transient error when the network call fails', async () => {
    const sender = makeSender(() => {
      throw new TypeError('network down');
    });

    await expect(sender.send({ text: 'x' })).rejects.toBeInstanceOf(TransientDeliveryError);
  });

  it('treats a 200 body with ok:false as transient', async () => {
    const sender = makeSender(() => jsonResponse({ ok: false, description: 'weird' }, 200));

    await expect(sender.send({ text: 'x' })).rejects.toBeInstanceOf(TransientDeliveryError);
  });

  it('falls back to the global fetch when none is injected', async () => {
    const fetchMock = async (): Promise<Response> => jsonResponse({ ok: true });
    const spy = spyOn(globalThis, 'fetch').mockImplementation(fetchMock as unknown as typeof fetch);
    try {
      const sender = new TelegramNotificationSender({
        botToken: 'B',
        chatId: '@c',
        baseUrl: 'https://tg.test',
      });

      await sender.send({ text: 'hi' });

      expect(spy).toHaveBeenCalledTimes(1);
      expect(String(spy.mock.calls[0]![0])).toBe('https://tg.test/botB/sendMessage');
    } finally {
      spy.mockRestore();
    }
  });
});

describe('TelegramNotificationSender forum topics', () => {
  function captureSender(options: { messageThreadId?: number }) {
    const captured: CapturedRequest[] = [];
    const fetchImpl: FetchLike = async (url, init) => {
      captured.push({ url, init });
      return jsonResponse({ ok: true });
    };
    const sender = new TelegramNotificationSender({
      botToken: 'B',
      chatId: '@c',
      baseUrl: 'https://tg.test',
      ...(options.messageThreadId !== undefined
        ? { messageThreadId: options.messageThreadId }
        : {}),
      fetch: fetchImpl,
    });
    return { sender, captured };
  }

  it('sends the default topic from options', async () => {
    const { sender, captured } = captureSender({ messageThreadId: 7 });

    await sender.send({ text: 'hi' });

    const payload = JSON.parse(String(captured[0]!.init.body));
    expect(payload.message_thread_id).toBe(7);
  });

  it('lets a notification override the default topic', async () => {
    const { sender, captured } = captureSender({ messageThreadId: 7 });

    await sender.send({ text: 'hi', messageThreadId: 42 });

    const payload = JSON.parse(String(captured[0]!.init.body));
    expect(payload.message_thread_id).toBe(42);
  });

  it('omits message_thread_id when neither default nor override is set', async () => {
    const { sender, captured } = captureSender({});

    await sender.send({ text: 'hi' });

    const payload = JSON.parse(String(captured[0]!.init.body));
    expect(payload.message_thread_id).toBeUndefined();
  });
});
