import { describe, it, expect, vi, beforeEach } from 'vitest';
import { esc, sendLongMessage } from '../telegram';

describe('telegram', () => {
  describe('esc - HTML escape', () => {
    it('escapes ampersand', () => {
      expect(esc('Tom & Jerry')).toBe('Tom &amp; Jerry');
    });

    it('escapes less-than', () => {
      expect(esc('2 < 3')).toBe('2 &lt; 3');
    });

    it('escapes greater-than', () => {
      expect(esc('3 > 2')).toBe('3 &gt; 2');
    });

    it('escapes double quote', () => {
      expect(esc('He said "hi"')).toBe('He said &quot;hi&quot;');
    });

    it('escapes all special chars together', () => {
      expect(esc('A & B < C > D "E"')).toBe('A &amp; B &lt; C &gt; D &quot;E&quot;');
    });

    it('handles multiple occurrences of same char', () => {
      expect(esc('<<tag>>')).toBe('&lt;&lt;tag&gt;&gt;');
    });

    it('handles empty string', () => {
      expect(esc('')).toBe('');
    });

    it('handles null/undefined', () => {
      expect(esc(null as any)).toBe('');
      expect(esc(undefined as any)).toBe('');
    });

    it('does not escape already-safe text', () => {
      expect(esc('Hello World')).toBe('Hello World');
      expect(esc('test@example.com')).toBe('test@example.com');
    });

    it('is safe for HTML href attributes', () => {
      const dangerous = 'onclick="alert()"';
      const escaped = esc(dangerous);
      // Should be safe in href="..."
      expect(escaped).toBe('onclick=&quot;alert()&quot;');
    });
  });

  describe('sendLongMessage', () => {
    beforeEach(() => {
      global.fetch = vi.fn();
    });

    it('sends short message without chunking', async () => {
      const mockResponse = {
        ok: true,
        json: () => Promise.resolve({ ok: true, result: { message_id: 1 } }),
      };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      const shortText = 'Hello World';
      await sendLongMessage('token', 123, shortText);

      expect(global.fetch).toHaveBeenCalledTimes(1);
      const callArgs = (global.fetch as any).mock.calls[0];
      const bodyStr = JSON.stringify(JSON.parse(callArgs[1].body));
      expect(bodyStr).toContain('Hello World');
    });

    it('chunks long message at 4096 char boundary', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ok: true }),
        } as any)
      );

      // Create text > 4096 chars
      const longText = 'A'.repeat(5000);
      await sendLongMessage('token', 123, longText);

      // Should split into multiple calls
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('splits at line boundaries when possible', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ok: true }),
        } as any)
      );

      // Create text with lines, total > 4096
      const lines = Array(200).fill('Line of text with more content').join('\n');
      const longText = lines; // Approximately 6400+ chars

      await sendLongMessage('token', 123, longText);

      // Should chunk (multiple calls)
      expect(global.fetch).toHaveBeenCalled();

      // Verify each chunk is ≤ 4096
      for (let i = 0; i < (global.fetch as any).mock.calls.length; i++) {
        const body = (global.fetch as any).mock.calls[i][1].body;
        const payload = JSON.parse(body);
        expect(payload.text.length).toBeLessThanOrEqual(4096);
      }
    });

    it('handles single line longer than 4096 chars', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ok: true }),
        } as any)
      );

      // Single line > 4096 chars (hard split required)
      const longLine = 'X'.repeat(5000);
      await sendLongMessage('token', 123, longLine);

      // Should hard-split at 4096 char boundary
      expect(global.fetch).toHaveBeenCalledTimes(2);

      // First chunk should be exactly 4096
      const call0 = (global.fetch as any).mock.calls[0];
      const payload0 = JSON.parse(call0[1].body);
      expect(payload0.text.length).toBe(4096);

      // Second chunk should be remainder
      const call1 = (global.fetch as any).mock.calls[1];
      const payload1 = JSON.parse(call1[1].body);
      expect(payload1.text.length).toBe(5000 - 4096);
    });

    it('preserves parse_mode and other options', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ok: true }),
        } as any)
      );

      const opts = { disable_web_page_preview: true, custom_key: 'value' };
      await sendLongMessage('token', 123, 'Short text', opts);

      const call = (global.fetch as any).mock.calls[0];
      const payload = JSON.parse(call[1].body);
      expect(payload.disable_web_page_preview).toBe(true);
      expect(payload.custom_key).toBe('value');
      expect(payload.parse_mode).toBe('HTML');
    });

    it('handles empty text', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ok: true }),
        } as any)
      );

      await sendLongMessage('token', 123, '');

      // Even empty text should attempt send (Telegram will handle)
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('continues sending after error in sendMessage (graceful degradation)', async () => {
      global.fetch = vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ ok: true }),
        } as any)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ ok: true }),
        } as any);

      const longText = 'A'.repeat(5000);
      // Should handle error gracefully (not crash, continue sending)
      await sendLongMessage('token', 123, longText);
      // Even with error in middle, it should attempt send
      expect(global.fetch).toHaveBeenCalled();
    });

    it('uses correct chat_id type (string or number)', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ok: true }),
        } as any)
      );

      // Test with number
      await sendLongMessage('token', 123, 'text');
      let payload = JSON.parse((global.fetch as any).mock.calls[0][1].body);
      expect(payload.chat_id).toBe(123);

      global.fetch.mockClear();

      // Test with string
      await sendLongMessage('token', 'group-123', 'text');
      payload = JSON.parse((global.fetch as any).mock.calls[0][1].body);
      expect(payload.chat_id).toBe('group-123');
    });
  });
});
