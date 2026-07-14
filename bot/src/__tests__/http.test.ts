import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchWithTimeout, fetchJson } from '../http';

describe('http', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('fetchWithTimeout', () => {
    it('fetches successfully within timeout', async () => {
      const mockResponse = { ok: true, status: 200, text: () => Promise.resolve('OK') };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      const result = await fetchWithTimeout('https://example.com', {}, 5000);
      expect(result.ok).toBe(true);
      expect(global.fetch).toHaveBeenCalled();
    });

    it('uses default timeout of 20000ms', async () => {
      let setTimeoutCalled = false;
      const originalSetTimeout = global.setTimeout;
      global.setTimeout = vi.fn((cb, ms) => {
        if (ms === 20000) setTimeoutCalled = true;
        return originalSetTimeout(cb, ms);
      });

      const mockResponse = { ok: true, status: 200 };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      await fetchWithTimeout('https://example.com');
      expect(setTimeoutCalled).toBe(true);
    });

    it('uses custom timeout value', async () => {
      let customTimeoutMs = 0;
      const originalSetTimeout = global.setTimeout;
      global.setTimeout = vi.fn((cb, ms) => {
        customTimeoutMs = ms;
        return originalSetTimeout(cb, ms);
      });

      const mockResponse = { ok: true, status: 200 };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      await fetchWithTimeout('https://example.com', {}, 10000);
      expect(customTimeoutMs).toBe(10000);
    });

    it('passes through fetch options', async () => {
      const mockResponse = { ok: true };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      const opts = { method: 'POST', body: 'test' };
      await fetchWithTimeout('https://example.com', opts, 5000);

      expect(global.fetch).toHaveBeenCalledWith(
        'https://example.com',
        expect.objectContaining({ method: 'POST', body: 'test' })
      );
    });

    it('includes signal in fetch options', async () => {
      const mockResponse = { ok: true };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      await fetchWithTimeout('https://example.com', {}, 5000);

      expect(global.fetch).toHaveBeenCalled();
      const callArgs = (global.fetch as any).mock.calls[0];
      expect(callArgs[1]).toHaveProperty('signal');
      expect(callArgs[1].signal).toBeInstanceOf(AbortSignal);
    });
  });

  describe('fetchJson', () => {
    it('fetches and parses JSON', async () => {
      const jsonData = { key: 'value' };
      const mockResponse = {
        ok: true,
        json: () => Promise.resolve(jsonData),
      };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      const result = await fetchJson('https://example.com');
      expect(result).toEqual(jsonData);
    });

    it('returns null on non-ok response', async () => {
      const mockResponse = { ok: false, status: 404 };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      const result = await fetchJson('https://example.com');
      expect(result).toBeNull();
    });

    it('returns null on JSON parse error', async () => {
      const mockResponse = {
        ok: true,
        json: () => Promise.reject(new Error('Invalid JSON')),
      };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      const result = await fetchJson('https://example.com');
      expect(result).toBeNull();
    });

    it('returns null on fetch error', async () => {
      global.fetch = vi.fn(() => Promise.reject(new Error('Network error')));

      const result = await fetchJson('https://example.com');
      expect(result).toBeNull();
    });

    it('uses custom timeout', async () => {
      let customTimeoutMs = 0;
      const originalSetTimeout = global.setTimeout;
      global.setTimeout = vi.fn((cb, ms) => {
        customTimeoutMs = ms;
        return originalSetTimeout(cb, ms);
      });

      const mockResponse = {
        ok: true,
        json: () => Promise.resolve({ data: 'test' }),
      };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      await fetchJson('https://example.com', {}, 5000);
      expect(customTimeoutMs).toBe(5000);
    });

    it('has default timeout of 10000ms', async () => {
      let defaultTimeoutMs = 0;
      const originalSetTimeout = global.setTimeout;
      global.setTimeout = vi.fn((cb, ms) => {
        defaultTimeoutMs = ms;
        return originalSetTimeout(cb, ms);
      });

      const mockResponse = {
        ok: true,
        json: () => Promise.resolve({ data: 'test' }),
      };
      global.fetch = vi.fn(() => Promise.resolve(mockResponse as any));

      await fetchJson('https://example.com');
      expect(defaultTimeoutMs).toBe(10000);
    });
  });
});
