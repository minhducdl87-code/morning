import { describe, it, expect } from 'vitest';
import { bytesToBase64, base64ToBytes } from '../binary';

describe('binary', () => {
  describe('bytesToBase64', () => {
    it('converts simple bytes to base64', () => {
      const bytes = new Uint8Array([72, 101, 108, 108, 111]); // "Hello"
      const b64 = bytesToBase64(bytes);
      expect(b64).toBe('SGVsbG8=');
    });

    it('round-trips through base64ToBytes', () => {
      const original = new Uint8Array([1, 2, 3, 255, 254, 253]);
      const b64 = bytesToBase64(original);
      const restored = base64ToBytes(b64);
      expect(restored).toEqual(original);
    });

    it('handles empty array', () => {
      const bytes = new Uint8Array([]);
      const b64 = bytesToBase64(bytes);
      expect(b64).toBe('');
    });

    it('handles large array (chunked)', () => {
      // Create array larger than chunkSize (0x8000 = 32768)
      const bytes = new Uint8Array(40000);
      for (let i = 0; i < bytes.length; i++) {
        bytes[i] = i % 256;
      }
      const b64 = bytesToBase64(bytes);
      const restored = base64ToBytes(b64);
      expect(restored).toEqual(bytes);
    });

    it('handles all byte values', () => {
      const bytes = new Uint8Array(256);
      for (let i = 0; i < 256; i++) {
        bytes[i] = i;
      }
      const b64 = bytesToBase64(bytes);
      const restored = base64ToBytes(b64);
      expect(restored).toEqual(bytes);
    });
  });

  describe('base64ToBytes', () => {
    it('converts base64 to bytes', () => {
      const b64 = 'SGVsbG8='; // "Hello"
      const bytes = base64ToBytes(b64);
      expect(bytes).toEqual(new Uint8Array([72, 101, 108, 108, 111]));
    });

    it('handles empty string', () => {
      const bytes = base64ToBytes('');
      expect(bytes.length).toBe(0);
    });

    it('handles padding variations', () => {
      // "Man" encodes to "TWFu" (no padding)
      // "M" encodes to "TQ==" (2 padding)
      const testCases = [
        { b64: 'TQ==', expected: [77] },
        { b64: 'TWE=', expected: [77, 97] },
        { b64: 'TWFu', expected: [77, 97, 110] },
      ];
      for (const { b64, expected } of testCases) {
        const bytes = base64ToBytes(b64);
        expect(Array.from(bytes)).toEqual(expected);
      }
    });
  });
});
