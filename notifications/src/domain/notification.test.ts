import { describe, expect, it } from 'bun:test';
import {
  createNotification,
  MAX_TEXT_LENGTH,
  NotificationValidationError,
  type NotificationCommand,
} from './notification';

describe('createNotification', () => {
  it('builds a notification from a minimal valid command', () => {
    const notification = createNotification({ text: 'hello world' });

    expect(notification.text).toBe('hello world');
    expect(notification.parseMode).toBeUndefined();
    expect(notification.disableNotification).toBeUndefined();
    expect(notification.disableWebPagePreview).toBeUndefined();
  });

  it('preserves all optional fields when provided', () => {
    const command: NotificationCommand = {
      text: 'formatted',
      parseMode: 'MarkdownV2',
      disableNotification: true,
      disableWebPagePreview: false,
    };

    const notification = createNotification(command);

    expect(notification).toEqual(command);
  });

  it('omits optional fields instead of storing undefined values', () => {
    const notification = createNotification({ text: 'x' });

    expect(Object.keys(notification)).toEqual(['text']);
  });

  it('accepts text exactly at the maximum length', () => {
    const text = 'a'.repeat(MAX_TEXT_LENGTH);

    const notification = createNotification({ text });

    expect(notification.text).toHaveLength(MAX_TEXT_LENGTH);
  });

  it('rejects an empty string', () => {
    expect(() => createNotification({ text: '' })).toThrow(NotificationValidationError);
  });

  it('rejects whitespace-only text', () => {
    expect(() => createNotification({ text: '   \n\t ' })).toThrow(NotificationValidationError);
  });

  it('rejects text longer than the maximum', () => {
    const text = 'a'.repeat(MAX_TEXT_LENGTH + 1);

    expect(() => createNotification({ text })).toThrow(/exceeds the maximum/);
  });

  it('rejects a non-string text value', () => {
    const command = { text: 123 } as unknown as NotificationCommand;

    expect(() => createNotification(command)).toThrow(NotificationValidationError);
  });
});
