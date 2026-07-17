const { test, expect } = require('@playwright/test');

const desktopViewports = [
  { name: '14-inch laptop', width: 1366, height: 768 },
  { name: '22-inch FHD monitor', width: 1920, height: 1080 },
  { name: '27-inch QHD monitor', width: 2560, height: 1440 }
];

async function waitForDigest(page) {
  await page.goto('/');
  await expect(page.locator('[data-story-id]').first()).toBeVisible();
}

for (const viewport of desktopViewports) {
  test(`${viewport.name} keeps the desktop briefing dashboard`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await waitForDigest(page);

    await expect(page.locator('#archive-pane')).toBeVisible();
    await expect(page.locator('#feed-pane')).toBeVisible();
    await expect(page.locator('.story-hero')).toBeVisible();
    await expect(page.locator('.story-primary')).toHaveCount(2);
    await expect(page.locator('#reader-pane')).not.toBeInViewport();
    await expect(page.locator('#reader-pane')).toHaveAttribute('aria-hidden', 'true');
    await expect(page.locator('#nav-toggle')).toBeHidden();

    const metrics = await page.evaluate(() => {
      const shell = document.querySelector('.app-shell');
      const style = getComputedStyle(shell);
      return {
        viewportWidth: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        shellWidth: shell.getBoundingClientRect().width,
        columns: style.gridTemplateColumns.split(' ').filter(Boolean).length,
        display: style.display
      };
    });

    expect(metrics.viewportWidth).toBe(viewport.width);
    expect(metrics.documentWidth).toBeLessThanOrEqual(viewport.width);
    expect(metrics.shellWidth).toBeGreaterThan(1100);
    expect(metrics.columns).toBe(2);
    expect(metrics.display).toBe('grid');

    await expect(page.locator('.story-card').first()).toBeVisible();
  });
}

test('dashboard hierarchy opens a single detail sheet without reordering stories', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await waitForDigest(page);

  const feedRows = page.locator('[data-story-id]');
  const firstTitle = (await feedRows.first().locator('.story-title').textContent()).trim();
  await feedRows.first().click();
  await expect(page.locator('#reader-pane')).toHaveClass(/open/);
  await expect(page.locator('[data-reader-article]:visible')).toHaveCount(1);
  await expect(page.locator('[data-reader-primary]')).toHaveCount(1);
  await expect(feedRows.first()).toHaveClass(/read/);
  await expect(feedRows.first()).toHaveAttribute('aria-label', /Đã đọc$/);
  await expect(feedRows.nth(1)).not.toHaveClass(/read/);
  await page.locator('[data-close-reader]').click();
  await expect(page.locator('[data-story-id]').first().locator('.story-title')).toHaveText(firstTitle);
});

test('top briefing slots diversify topics without displacing the lead story', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await waitForDigest(page);

  const result = await page.evaluate(() => {
    const make = (id, topicField) => ({ id, topicField, isHot: false, detail: '' });
    const ranked = rankDashboardItems([
      make('v1', 'vietnam'), make('v2', 'vietnam'), make('v3', 'vietnam'),
      make('f1', 'finance'), make('f2', 'finance'),
      make('t1', 'tech'), make('t2', 'tech'), make('l1', 'lifestyle')
    ]);
    const singleTopic = rankDashboardItems([make('v1', 'vietnam'), make('v2', 'vietnam'), make('v3', 'vietnam')]);
    return {
      ids: ranked.map(item => item.id),
      topics: ranked.slice(0, 6).map(item => item.topicField),
      singleTopicIds: singleTopic.map(item => item.id)
    };
  });
  const topTopics = result.topics;
  const counts = topTopics.reduce((result, topic) => {
    result[topic] = (result[topic] || 0) + 1;
    return result;
  }, {});

  expect(result.ids[0]).toBe('v1');
  expect(new Set(topTopics).size).toBeGreaterThanOrEqual(3);
  expect(Math.max(...Object.values(counts))).toBeLessThanOrEqual(2);
  expect(result.singleTopicIds).toEqual(['v1', 'v2', 'v3']);
});

test('mobile uses list-to-reader without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await waitForDigest(page);

  await expect(page.locator('#nav-toggle')).toBeVisible();
  await expect(page.locator('#archive-pane')).not.toBeInViewport();
  await expect(page.locator('#reader-pane')).not.toBeInViewport();
  await expect(page.locator('#archive-pane')).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('#archive-pane')).toHaveAttribute('inert', '');
  await expect(page.locator('#reader-pane')).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('#reader-pane')).toHaveAttribute('inert', '');

  await page.locator('#nav-toggle').click();
  await expect(page.locator('#archive-pane')).toHaveAttribute('aria-hidden', 'false');
  await expect(page.locator('#archive-pane')).not.toHaveAttribute('inert', '');
  await expect(page.locator('#archive-pane')).toHaveAttribute('aria-modal', 'true');
  await expect(page.locator('#feed-pane')).toHaveAttribute('inert', '');
  await expect(page.locator('.topbar')).toHaveAttribute('inert', '');
  await page.locator('#nav-close').click();
  await expect(page.locator('#nav-toggle')).toBeFocused();
  await expect(page.locator('#feed-pane')).not.toHaveAttribute('inert', '');

  await page.locator('#nav-toggle').click();
  await page.locator('.topic-nav-link').first().click();
  await expect(page.locator('#archive-pane')).toHaveAttribute('inert', '');
  await expect(page.locator('#nav-toggle')).toBeFocused();

  const firstStory = page.locator('[data-story-id]').first();
  await firstStory.click();
  await expect(page.locator('#reader-pane')).toHaveClass(/open/);
  await expect(page.locator('[data-close-reader]')).toBeVisible();
  await expect(page.locator('#reader-pane')).toHaveAttribute('aria-modal', 'true');
  await expect(page.locator('#reader-pane')).toHaveAttribute('aria-hidden', 'false');
  await expect(page.locator('#reader-pane')).not.toHaveAttribute('inert', '');
  await expect(page.locator('#feed-pane')).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('#feed-pane')).toHaveAttribute('inert', '');

  const metrics = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth
  }));
  expect(metrics.documentWidth).toBeLessThanOrEqual(metrics.viewportWidth);

  await page.locator('[data-close-reader]').click();
  await expect(page.locator('#reader-pane')).not.toHaveClass(/open/);
  await expect(page.locator('#reader-pane')).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('#reader-pane')).toHaveAttribute('inert', '');
  await expect(page.locator('#feed-pane')).toHaveAttribute('aria-hidden', 'false');
  await expect(firstStory).toBeFocused();
});

test('resizing out of archive overlay mode keeps the detail sheet closed', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await waitForDigest(page);
  await page.locator('#nav-toggle').click();

  await page.setViewportSize({ width: 1366, height: 768 });
  await expect(page.locator('#archive-pane')).toHaveAttribute('aria-hidden', 'false');
  await expect(page.locator('#archive-pane')).not.toHaveAttribute('inert', '');
  await expect(page.locator('#reader-pane')).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('#reader-pane')).toHaveAttribute('inert', '');
});

test('editorial ranking stays stable after marking stories read', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await waitForDigest(page);
  const titleBefore = (await page.locator('.story-hero .story-title').textContent()).trim();
  await expect(page.locator('.story-hero .story-meta span').first()).toContainText('Việt Nam');
  await page.locator('#mark-all-read').click();
  await expect(page.locator('.story-hero .story-title')).toHaveText(titleBefore);
});

test('monthly repository metadata survives flattening and renders in the reader', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await waitForDigest(page);

  const monthlyHref = await page.locator('a[href^="#month-"]').first().getAttribute('href');
  expect(monthlyHref).toBeTruthy();
  await page.evaluate(hash => { location.hash = hash; }, monthlyHref);

  const primaryReader = page.locator('[data-reader-primary]');
  await expect(primaryReader.locator('[data-reader-stars]')).toBeVisible();
  await expect(primaryReader.locator('[data-reader-verdict]')).toBeVisible();
  await expect(primaryReader.locator('[data-reader-reason]')).toBeVisible();
});

test('reader separates feed summary from detail and labels legacy fallback honestly', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await waitForDigest(page);

  const rendered = await page.evaluate(() => {
    const synthetic = {
      id: 'synthetic-detail', title: 'Một tiêu đề kiểm thử', desc: 'Tóm tắt để quét nhanh.',
      detail: 'Chi tiết dài hơn, bổ sung bối cảnh. Phần này không lặp lại nguyên văn tóm tắt.',
      sourceName: 'Nguồn kiểm thử', sourceDate: '', topicLabel: 'Kiểm thử', tag: '', url: 'https://example.com'
    };
    const legacy = { ...synthetic, detail: '' };
    const root = document.createElement('div');
    root.innerHTML = readerHtml(synthetic, 0, 1);
    const detail = root.querySelector('[data-reader-copy]');
    root.innerHTML = readerHtml(legacy, 0, 1);
    return {
      detailText: detail.textContent,
      detailKind: detail.dataset.contentKind,
      fallbackKind: root.querySelector('[data-reader-copy]').dataset.contentKind,
      fallbackDisclosure: root.querySelector('.reader-disclosure').textContent
    };
  });

  expect(rendered.detailText).toContain('bổ sung bối cảnh');
  expect(rendered.detailKind).toBe('detail');
  expect(rendered.fallbackKind).toBe('summary');
  expect(rendered.fallbackDisclosure).toContain('chỉ lưu bản tóm tắt');
});

test('reader navigation stays fixed across desktop, adaptive, and mobile layouts', async ({ page }) => {
  for (const viewport of [
    { width: 1366, height: 768 },
    { width: 1180, height: 768 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport);
    await waitForDigest(page);
    await page.locator('[data-story-id]').first().click();

    const nav = page.locator('.reader-nav');
    const pane = page.locator('#reader-pane');
    const initialNav = await nav.boundingBox();
    const paneBox = await pane.boundingBox();
    expect(initialNav).toBeTruthy();
    expect(Math.abs(initialNav.y + initialNav.height - (paneBox.y + paneBox.height))).toBeLessThanOrEqual(1);

    await page.locator('[data-reader-step="1"]').click();
    const changedNav = await nav.boundingBox();
    expect(Math.abs(changedNav.y - initialNav.y)).toBeLessThanOrEqual(1);
    expect(Math.abs(changedNav.height - initialNav.height)).toBeLessThanOrEqual(1);

    await page.locator('.reader-scroll').first().evaluate(node => { node.scrollTop = node.scrollHeight; });
    const scrolledNav = await nav.boundingBox();
    expect(Math.abs(scrolledNav.y - initialNav.y)).toBeLessThanOrEqual(1);
  }
});

test('reader keyboard navigation restores focus after replacing story content', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await waitForDigest(page);
  await page.locator('[data-story-id]').first().click();

  await page.keyboard.press('Alt+ArrowDown');
  await expect(page.locator('[data-reader-step="1"]')).toBeFocused();
  await expect.poll(() => page.locator('.reader-scroll').first().evaluate(node => node.scrollTop)).toBe(0);
});

test('dashboard grid adapts without horizontal overflow', async ({ page }) => {
  const cases = [
    { width: 390, expected: 1 },
    { width: 900, expected: 2 },
    { width: 1180, expected: 2 },
    { width: 1366, expected: 3 },
    { width: 1920, expected: 4 },
    { width: 2560, expected: 4 }
  ];

  for (const item of cases) {
    await page.setViewportSize({ width: item.width, height: 900 });
    await waitForDigest(page);
    const columns = await page.locator('.compact-grid').evaluate(grid => getComputedStyle(grid).gridTemplateColumns.split(' ').filter(Boolean).length);
    expect(columns).toBe(item.expected);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBeFalsy();
  }
});

test('wide dashboard keeps a balanced lead row and fills supporting sections', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await waitForDigest(page);

  const metrics = await page.evaluate(() => {
    const hero = document.querySelector('.story-hero').getBoundingClientRect();
    const primary = document.querySelector('.primary-stack').getBoundingClientRect();
    const secondary = document.querySelector('.secondary-grid').getBoundingClientRect();
    const secondaryCards = Array.from(document.querySelectorAll('.secondary-grid .story-card'));
    const lastSecondary = secondaryCards.at(-1).getBoundingClientRect();
    const headlinePanel = document.querySelector('.headline-panel').getBoundingClientRect();
    const firstHeadline = document.querySelector('.headline-list .story-card').getBoundingClientRect();
    return {
      leadRatio: hero.width / primary.width,
      secondaryGap: Math.abs(secondary.right - lastSecondary.right),
      headlineFill: firstHeadline.width / headlinePanel.width
    };
  });

  expect(metrics.leadRatio).toBeGreaterThan(1.3);
  expect(metrics.leadRatio).toBeLessThan(1.65);
  expect(metrics.secondaryGap).toBeLessThan(2);
  expect(metrics.headlineFill).toBeGreaterThan(0.98);
});

test('image-less cards use compact topic markers while real images retain visual space', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  await waitForDigest(page);

  const ratios = await page.locator('.story-primary').evaluateAll(cards => cards.map(card => {
    const visual = card.querySelector('.story-visual').getBoundingClientRect();
    const body = card.querySelector('.story-card-body').getBoundingClientRect();
    return visual.width / (visual.width + body.width);
  }));

  expect(ratios).toHaveLength(2);
  for (const ratio of ratios) expect(ratio).toBeLessThan(0.06);

  const imageRatio = await page.locator('.story-primary').first().evaluate(card => {
    card.querySelector('.story-visual').classList.add('has-image');
    const visual = card.querySelector('.story-visual').getBoundingClientRect();
    const body = card.querySelector('.story-card-body').getBoundingClientRect();
    return visual.width / (visual.width + body.width);
  });
  expect(imageRatio).toBeGreaterThan(0.36);
  expect(imageRatio).toBeLessThan(0.42);

  const secondaryFallbacks = await page.locator('.story-secondary .story-visual:not(.has-image)').evaluateAll(visuals => visuals.map(visual => ({
    height: visual.getBoundingClientRect().height,
    monogramVisible: getComputedStyle(visual.querySelector('.visual-monogram')).display !== 'none'
  })));
  expect(secondaryFallbacks).toHaveLength(3);
  for (const fallback of secondaryFallbacks) {
    expect(fallback.height).toBeLessThan(52);
    expect(fallback.monogramVisible).toBe(false);
  }
});

test('hero and light surfaces preserve readable contrast after read state', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await waitForDigest(page);

  const hero = page.locator('.story-hero');
  const title = hero.locator('.story-title');
  const titleColorBefore = await title.evaluate(node => getComputedStyle(node).color);
  await hero.click();
  await page.locator('[data-close-reader]').click();
  await expect(hero).toHaveClass(/read/);
  await expect(title).toHaveCSS('color', titleColorBefore);

  const ratios = await page.evaluate(() => {
    const parse = value => {
      const color = value.trim();
      if (color.startsWith('#')) {
        const hex = color.slice(1);
        return [0, 2, 4].map(offset => Number.parseInt(hex.slice(offset, offset + 2), 16));
      }
      return color.match(/[\d.]+/g).slice(0, 3).map(Number);
    };
    const luminance = rgb => {
      const channels = rgb.map(value => {
        const channel = value / 255;
        return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    };
    const contrast = (a, b) => {
      const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
      return (light + 0.05) / (dark + 0.05);
    };
    const root = getComputedStyle(document.documentElement);
    return {
      muted: contrast(parse(root.getPropertyValue('--muted')), parse(root.getPropertyValue('--surface'))),
      faint: contrast(parse(root.getPropertyValue('--faint')), parse(root.getPropertyValue('--bg')))
    };
  });

  expect(ratios.muted).toBeGreaterThanOrEqual(4.5);
  expect(ratios.faint).toBeGreaterThanOrEqual(4.5);
});

test('read cards lose elevation without sacrificing text contrast in either theme', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await waitForDigest(page);

  for (const theme of ['light', 'dark']) {
    await page.evaluate(nextTheme => { document.body.dataset.theme = nextTheme; }, theme);
    const state = await page.locator('.story-secondary').first().evaluate(card => {
      card.style.transition = 'none';
      const snapshot = () => {
        const cardStyle = getComputedStyle(card);
        const actionStyle = getComputedStyle(card.querySelector('.story-action'));
        return { background: cardStyle.backgroundColor, shadow: cardStyle.boxShadow, action: actionStyle.color };
      };
      card.classList.remove('read');
      const unread = snapshot();
      card.classList.add('read');
      const read = snapshot();
      return { unread, read };
    });

    expect(state.read.background).not.toBe(state.unread.background);
    expect(state.read.shadow).not.toBe(state.unread.shadow);
    expect(state.read.action).not.toBe(state.unread.action);
  }
});

test('responsive boundaries preserve desktop, adaptive, and mobile contracts', async ({ page }) => {
  const cases = [
    { width: 1181, columns: 2, navVisible: false, readerInViewport: false },
    { width: 1180, columns: 1, navVisible: true, readerInViewport: false },
    { width: 901, columns: 1, navVisible: true, readerInViewport: false },
    { width: 900, columns: 1, navVisible: true, readerInViewport: false }
  ];

  for (const item of cases) {
    await page.setViewportSize({ width: item.width, height: 768 });
    await waitForDigest(page);
    await expect(page.locator('#nav-toggle'))[item.navVisible ? 'toBeVisible' : 'toBeHidden']();
    const readerInViewport = await page.locator('#reader-pane').evaluate(reader => {
      const rect = reader.getBoundingClientRect();
      return rect.right > 0 && rect.left < window.innerWidth && rect.bottom > 0 && rect.top < window.innerHeight;
    });
    expect(readerInViewport).toBe(item.readerInViewport);
    const columns = await page.locator('.app-shell').evaluate(shell => {
      const style = getComputedStyle(shell);
      return style.display === 'grid' ? style.gridTemplateColumns.split(' ').filter(Boolean).length : 1;
    });
    expect(columns).toBe(item.columns);
  }
});

test('search filters the live feed', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await waitForDigest(page);

  const firstTitle = (await page.locator('.story-title').first().textContent()).trim();
  const query = firstTitle.split(/\s+/).find(word => word.length >= 5) || firstTitle;
  await page.locator('#search-input').fill(query);

  await expect(page.locator('[data-story-id]').first()).toBeVisible();
  const titles = await page.locator('.story-title').allTextContents();
  expect(titles.length).toBeGreaterThan(0);
  expect(titles.some(title => title.toLocaleLowerCase('vi').includes(query.toLocaleLowerCase('vi')))).toBeTruthy();
});

test('search matches Vietnamese text without diacritics', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await waitForDigest(page);

  const fold = value => value.normalize('NFD').replace(/\p{Diacritic}/gu, '').replace(/đ/g, 'd').replace(/Đ/g, 'D');
  const titlesBeforeSearch = await page.locator('.story-title').allTextContents();
  const accentedWord = titlesBeforeSearch
    .flatMap(title => title.split(/\s+/))
    .find(word => word.length >= 3 && fold(word) !== word);
  expect(accentedWord).toBeTruthy();
  const query = fold(accentedWord);
  await page.locator('#search-input').fill(query);

  await expect(page.locator('[data-story-id]').first()).toBeVisible();
  const titles = await page.locator('.story-title').allTextContents();
  expect(titles.some(item => fold(item).toLocaleLowerCase('vi').includes(query.toLocaleLowerCase('vi')))).toBeTruthy();
});

test('loading, empty search, and completed read states are actionable and announced', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.route('**/cards.json?*', async route => {
    await new Promise(resolve => setTimeout(resolve, 500));
    await route.continue();
  });

  const navigation = page.goto('/');
  await expect(page.locator('#feed-list')).toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('.loading-dashboard')).toBeVisible();
  await navigation;
  await expect(page.locator('[data-story-id]').first()).toBeVisible();
  await expect(page.locator('#feed-list')).toHaveAttribute('aria-busy', 'false');

  await page.locator('#search-input').fill('khong-co-ket-qua-chac-chan');
  await expect(page.locator('.state-filter')).toBeVisible();
  await expect(page.locator('[data-reset-feed]')).toBeVisible();
  await page.locator('[data-reset-feed]').click();
  await expect(page.locator('#search-input')).toHaveValue('');
  await expect(page.locator('#search-input')).toBeFocused();
  await expect(page.locator('.story-hero')).toBeVisible();

  const markAll = page.locator('#mark-all-read');
  await markAll.click();
  await expect(markAll).toBeDisabled();
  await expect(markAll).toHaveText('Đã đọc tất cả');
});

test('critical data failure renders a clear retry state instead of an empty dashboard', async ({ page }) => {
  await page.route('**/cards.json?*', route => route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }));
  await page.goto('/');

  await expect(page.locator('#feed-list')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('.state-error')).toBeVisible();
  await expect(page.locator('[data-retry-load]')).toHaveText('Thử tải lại');
  await expect(page.locator('#feed-title')).toHaveText('Bản tin tạm gián đoạn');
  await expect(page.locator('[data-story-id]')).toHaveCount(0);
});

test('current archive and topic selections expose semantic state', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await waitForDigest(page);

  await expect(page.locator('.archive-link.active')).toHaveAttribute('aria-current', 'page');
  await expect(page.locator('.topic-chip.active')).toHaveAttribute('aria-pressed', 'true');
  const nextTopic = page.locator('.topic-chip').nth(1);
  await nextTopic.click();
  await expect(nextTopic).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.topic-chip').first()).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('.topic-nav-link.active')).toHaveAttribute('aria-pressed', 'true');
});
