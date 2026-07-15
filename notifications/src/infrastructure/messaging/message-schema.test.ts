import { describe, expect, it } from 'bun:test';
import { parseNotificationMessage } from './message-schema';

describe('parseNotificationMessage', () => {
  it('accepts a minimal valid object', () => {
    const result = parseNotificationMessage({ text: 'hello' });

    expect(result).toEqual({ ok: true, command: { text: 'hello' } });
  });

  it('accepts all supported fields', () => {
    const result = parseNotificationMessage({
      text: 'hi',
      parseMode: 'MarkdownV2',
      disableNotification: true,
      disableWebPagePreview: false,
      messageThreadId: 2,
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.command).toEqual({
        text: 'hi',
        parseMode: 'MarkdownV2',
        disableNotification: true,
        disableWebPagePreview: false,
        messageThreadId: 2,
      });
    }
  });

  it('rejects a non-positive messageThreadId', () => {
    expect(parseNotificationMessage({ text: 'hi', messageThreadId: 0 }).ok).toBe(false);
    expect(parseNotificationMessage({ text: 'hi', messageThreadId: -1 }).ok).toBe(false);
    const result = parseNotificationMessage({ text: 'hi', messageThreadId: 'two' });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.reason).toContain('messageThreadId');
  });

  it('parses a JSON string body', () => {
    const result = parseNotificationMessage('{"text":"from string"}');

    expect(result).toEqual({ ok: true, command: { text: 'from string' } });
  });

  it('parses a Buffer body', () => {
    const result = parseNotificationMessage(Buffer.from('{"text":"from buffer"}', 'utf8'));

    expect(result).toEqual({ ok: true, command: { text: 'from buffer' } });
  });

  it('strips unknown keys', () => {
    const result = parseNotificationMessage({ text: 'hi', extra: 'ignored', foo: 42 });

    expect(result).toEqual({ ok: true, command: { text: 'hi' } });
  });

  it('rejects a missing text field', () => {
    const result = parseNotificationMessage({ parseMode: 'HTML' });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.reason).toContain('text');
  });

  it('rejects a non-string text field', () => {
    const result = parseNotificationMessage({ text: 123 });

    expect(result.ok).toBe(false);
  });

  it('rejects an invalid parseMode', () => {
    const result = parseNotificationMessage({ text: 'hi', parseMode: 'BBCode' });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.reason).toContain('parseMode');
  });

  it('rejects a non-JSON string', () => {
    const result = parseNotificationMessage('not json at all');

    expect(result).toEqual({ ok: false, reason: 'message body is not a JSON object' });
  });

  it('rejects a JSON array', () => {
    const result = parseNotificationMessage('[1,2,3]');

    expect(result.ok).toBe(false);
  });

  it('rejects null and primitive bodies', () => {
    expect(parseNotificationMessage(null).ok).toBe(false);
    expect(parseNotificationMessage(42).ok).toBe(false);
    expect(parseNotificationMessage(undefined).ok).toBe(false);
  });
});
