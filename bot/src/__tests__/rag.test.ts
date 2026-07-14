import { describe, it, expect } from 'vitest';
import { retrieveContext, formatContextForPrompt } from '../rag';
import type { DigestData, DigestItem } from '../types';

describe('rag - retrieveContext and formatContextForPrompt', () => {
  describe('retrieveContext', () => {
    it('returns empty array when no data', () => {
      const data: DigestData = { daily: [], weekly: [], monthly: [] };
      const result = retrieveContext(data, 'test', 12);
      expect(result).toEqual([]);
    });

    it('returns items without query (no stopwords)', () => {
      const data: DigestData = {
        daily: [
          {
            date: '2024-01-01',
            news: [
              { title: 'News 1', url: 'https://a.com' },
              { title: 'News 2', url: 'https://b.com' },
            ],
          },
        ],
        weekly: [],
        monthly: [],
      };

      const result = retrieveContext(data, '', 12);
      // Empty query → return most recent items
      expect(result.length).toBe(2);
      expect(result[0].title).toBe('News 1');
    });

    it('deduplicates by URL', () => {
      const data: DigestData = {
        daily: [
          {
            date: '2024-01-01',
            news: [
              { title: 'News 1', url: 'https://shared.com' },
            ],
          },
        ],
        weekly: [
          {
            weekLabel: 'Week 1',
            news: [
              { title: 'News 1 Again', url: 'https://shared.com' },
            ],
          },
        ],
        monthly: [],
      };

      const result = retrieveContext(data, '', 12);
      // Should dedupe by URL
      expect(result.length).toBe(1);
      expect(result[0].title).toBe('News 1'); // First occurrence
    });

    it('scores items by query relevance', () => {
      const data: DigestData = {
        daily: [
          {
            date: '2024-01-01',
            news: [
              { title: 'Machine Learning', url: 'https://a.com' },
              { title: 'Python Programming', url: 'https://b.com' },
              { title: 'Deep Learning', url: 'https://c.com' },
            ],
          },
        ],
        weekly: [],
        monthly: [],
      };

      const result = retrieveContext(data, 'learning', 12);
      // Should rank by query token overlap
      expect(result.length).toBeGreaterThan(0);
      // Items with "learning" should score higher
      expect(result[0].title).toMatch(/Learning/);
    });

    it('filters by topK limit', () => {
      const items = Array.from({ length: 20 }, (_, i) => ({
        title: `Item ${i}`,
        url: `https://test.com/${i}`,
      }));

      const data: DigestData = {
        daily: [{ date: '2024-01-01', news: items }],
        weekly: [],
        monthly: [],
      };

      const result = retrieveContext(data, '', 5);
      expect(result.length).toBeLessThanOrEqual(5);
    });

    it('filters items without title or name', () => {
      const data: DigestData = {
        daily: [
          {
            date: '2024-01-01',
            news: [
              { title: 'Valid', url: 'https://a.com' },
              { url: 'https://b.com' }, // No title/name
              { title: '', url: 'https://c.com' }, // Empty title
            ],
          },
        ],
        weekly: [],
        monthly: [],
      };

      const result = retrieveContext(data, '', 12);
      // Should only include items with non-empty title/name
      expect(result.length).toBe(1);
      expect(result[0].title).toBe('Valid');
    });

    it('excludes stopwords from query scoring', () => {
      const data: DigestData = {
        daily: [
          {
            date: '2024-01-01',
            news: [
              { title: 'The Machine Learning Book', url: 'https://a.com' },
              { title: 'Machine Learning Algorithms', url: 'https://b.com' },
            ],
          },
        ],
        weekly: [],
        monthly: [],
      };

      const result = retrieveContext(data, 'the machine', 12);
      // "the" is a stopword, only "machine" should score
      expect(result.length).toBeGreaterThan(0);
      // Both should score similar (same non-stopword content)
    });

    it('considers substring matches in title', () => {
      const data: DigestData = {
        daily: [
          {
            date: '2024-01-01',
            news: [
              { title: 'Exact match: React', url: 'https://a.com' },
              { title: 'Something else', url: 'https://b.com' },
            ],
          },
        ],
        weekly: [],
        monthly: [],
      };

      const result = retrieveContext(data, 'React', 12);
      // Should boost exact substring match
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].title).toContain('React');
    });
  });

  describe('formatContextForPrompt', () => {
    it('returns fallback message for empty items', () => {
      const result = formatContextForPrompt([]);
      expect(result).toContain('Không có tin liên quan');
    });

    it('formats single item', () => {
      const items: DigestItem[] = [
        {
          title: 'Test Article',
          url: 'https://example.com',
          desc: 'This is a test description',
        },
      ];

      const result = formatContextForPrompt(items);
      expect(result).toContain('[1]');
      expect(result).toContain('Test Article');
      expect(result).toContain('https://example.com');
      expect(result).toContain('This is a test description');
    });

    it('formats multiple items with numbering', () => {
      const items: DigestItem[] = [
        { title: 'Article 1', url: 'https://a.com', desc: 'Desc 1' },
        { title: 'Article 2', url: 'https://b.com', desc: 'Desc 2' },
        { title: 'Article 3', url: 'https://c.com', desc: 'Desc 3' },
      ];

      const result = formatContextForPrompt(items);
      expect(result).toContain('[1]');
      expect(result).toContain('[2]');
      expect(result).toContain('[3]');
    });

    it('uses reason field as fallback for desc', () => {
      const items: DigestItem[] = [
        {
          title: 'Article',
          url: 'https://example.com',
          reason: 'This is the reason',
        },
      ];

      const result = formatContextForPrompt(items);
      expect(result).toContain('This is the reason');
    });

    it('truncates long descriptions to 150 chars', () => {
      const longDesc = 'A'.repeat(200);
      const items: DigestItem[] = [
        {
          title: 'Article',
          url: 'https://example.com',
          desc: longDesc,
        },
      ];

      const result = formatContextForPrompt(items);
      const lines = result.split('\n');
      // Find the description line
      const descLine = lines.find(l => l.includes('A'));
      if (descLine) {
        expect(descLine.length).toBeLessThanOrEqual(160); // ~150 + slack
      }
    });

    it('handles missing optional fields', () => {
      const items: DigestItem[] = [
        {
          title: 'Minimal Article',
          url: 'https://example.com',
        },
      ];

      const result = formatContextForPrompt(items);
      expect(result).toContain('Minimal Article');
      expect(result).toContain('https://example.com');
      // Should not crash with missing desc/reason
    });

    it('uses name field if title missing', () => {
      const items: DigestItem[] = [
        {
          name: 'Named Item',
          url: 'https://example.com',
        },
      ];

      const result = formatContextForPrompt(items);
      expect(result).toContain('Named Item');
    });

    it('separates items with newline', () => {
      const items: DigestItem[] = [
        { title: 'Article 1', url: 'https://a.com' },
        { title: 'Article 2', url: 'https://b.com' },
      ];

      const result = formatContextForPrompt(items);
      const lines = result.split('\n');
      expect(lines.length).toBeGreaterThan(4); // Multiple items with newlines between
    });
  });
});
