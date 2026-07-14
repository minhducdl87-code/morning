import { describe, it, expect } from 'vitest';
import { getUpdateMessage } from '../telegram-types';
import type { TgUpdate, TgMessage } from '../telegram-types';

describe('telegram-types', () => {
  describe('getUpdateMessage', () => {
    it('returns message from update with message field', () => {
      const message: TgMessage = {
        message_id: 123,
        chat: { id: 456, type: 'private' },
        date: 1704067200,
        text: 'Hello',
      };

      const update: TgUpdate = {
        update_id: 1,
        message,
      };

      const result = getUpdateMessage(update);
      expect(result).toEqual(message);
      expect(result?.text).toBe('Hello');
    });

    it('returns edited_message when message is missing', () => {
      const editedMessage: TgMessage = {
        message_id: 123,
        chat: { id: 456, type: 'private' },
        date: 1704067200,
        text: 'Edited text',
      };

      const update: TgUpdate = {
        update_id: 1,
        edited_message: editedMessage,
      };

      const result = getUpdateMessage(update);
      expect(result).toEqual(editedMessage);
      expect(result?.text).toBe('Edited text');
    });

    it('prefers message over edited_message', () => {
      const message: TgMessage = {
        message_id: 123,
        chat: { id: 456, type: 'private' },
        date: 1704067200,
        text: 'Original',
      };

      const editedMessage: TgMessage = {
        message_id: 123,
        chat: { id: 456, type: 'private' },
        date: 1704067200,
        text: 'Edited',
      };

      const update: TgUpdate = {
        update_id: 1,
        message,
        edited_message: editedMessage,
      };

      const result = getUpdateMessage(update);
      expect(result).toEqual(message);
      expect(result?.text).toBe('Original');
    });

    it('returns null when neither message nor edited_message', () => {
      const update: TgUpdate = {
        update_id: 1,
      };

      const result = getUpdateMessage(update);
      expect(result).toBeNull();
    });

    it('returns null when both are undefined', () => {
      const update: TgUpdate = {
        update_id: 1,
        message: undefined,
        edited_message: undefined,
      };

      const result = getUpdateMessage(update);
      expect(result).toBeNull();
    });

    it('handles message with text field', () => {
      const message: TgMessage = {
        message_id: 100,
        chat: { id: 200, type: 'group' },
        date: 1704067200,
        text: 'Message content',
      };

      const update: TgUpdate = {
        update_id: 50,
        message,
      };

      const result = getUpdateMessage(update);
      expect(result?.message_id).toBe(100);
      expect(result?.chat.id).toBe(200);
      expect(result?.text).toBe('Message content');
    });

    it('handles message with caption field', () => {
      const message: TgMessage = {
        message_id: 100,
        chat: { id: 200, type: 'private' },
        date: 1704067200,
        caption: 'Photo caption',
        photo: [
          {
            file_id: 'file123',
            file_unique_id: 'unique123',
            width: 800,
            height: 600,
          },
        ],
      };

      const update: TgUpdate = {
        update_id: 50,
        message,
      };

      const result = getUpdateMessage(update);
      expect(result?.caption).toBe('Photo caption');
      expect(result?.photo).toBeDefined();
    });

    it('handles message with voice field', () => {
      const message: TgMessage = {
        message_id: 100,
        chat: { id: 200, type: 'private' },
        date: 1704067200,
        voice: {
          file_id: 'voice123',
          file_unique_id: 'unique123',
          duration: 30,
        },
      };

      const update: TgUpdate = {
        update_id: 50,
        message,
      };

      const result = getUpdateMessage(update);
      expect(result?.voice?.duration).toBe(30);
    });

    it('handles message with from field', () => {
      const message: TgMessage = {
        message_id: 100,
        from: {
          id: 999,
          is_bot: false,
          first_name: 'John',
        },
        chat: { id: 200, type: 'private' },
        date: 1704067200,
        text: 'Test',
      };

      const update: TgUpdate = {
        update_id: 50,
        message,
      };

      const result = getUpdateMessage(update);
      expect(result?.from?.id).toBe(999);
      expect(result?.from?.first_name).toBe('John');
    });

    it('handles edge case with minimal message', () => {
      const message: TgMessage = {
        message_id: 1,
        chat: { id: 1, type: 'private' },
        date: 1704067200,
      };

      const update: TgUpdate = {
        update_id: 1,
        message,
      };

      const result = getUpdateMessage(update);
      expect(result?.message_id).toBe(1);
      expect(result?.chat.id).toBe(1);
      expect(result?.text).toBeUndefined();
    });

    it('edited_message is returned only when message is null', () => {
      const editedMessage: TgMessage = {
        message_id: 50,
        chat: { id: 100, type: 'group' },
        date: 1704067200,
        text: 'Edited content',
      };

      const update: TgUpdate = {
        update_id: 25,
        edited_message: editedMessage,
      };

      const result = getUpdateMessage(update);
      expect(result).toBe(editedMessage);
    });
  });
});
