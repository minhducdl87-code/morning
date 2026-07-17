// App state, data loading, and interaction bindings.

let TOPICS = {};
let CONFIG = {};
let STATE = { views: [], byId: {}, dailyViews: [], currentWeek: '', defaultId: '' };
const READ_STORE = 'morning-desk:read:v1';
const THEME_STORE = 'morning-desk:theme';
const UI = {
  currentView: null,
  allItems: [],
  filteredItems: [],
  topicCounts: [],
  topic: 'all',
  query: '',
  selectedId: '',
  readIds: new Set(loadStoredArray(READ_STORE)),
  lastFeedTrigger: null
};

function loadStoredArray(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(value) ? value : [];
  } catch (_) {
    return [];
  }
}

function persistReadIds() {
  try { localStorage.setItem(READ_STORE, JSON.stringify(Array.from(UI.readIds).slice(-1000))); } catch (_) {}
}

function announce(message) {
  document.getElementById('live-region').textContent = message;
}

function setTheme(theme) {
  const isDark = theme === 'dark';
  document.body.toggleAttribute('data-theme', isDark);
  if (isDark) document.body.setAttribute('data-theme', 'dark');
  document.getElementById('theme-toggle').setAttribute('aria-pressed', String(isDark));
  document.querySelector('meta[name="theme-color"]').content = isDark ? '#101512' : '#f4f7f5';
  try { localStorage.setItem(THEME_STORE, isDark ? 'dark' : 'light'); } catch (_) {}
}

function setAccessibleHidden(element, hidden) {
  element.inert = hidden;
  element.setAttribute('aria-hidden', String(hidden));
}

function syncResponsivePaneState() {
  const archive = document.getElementById('archive-pane');
  const reader = document.getElementById('reader-pane');
  const feed = document.getElementById('feed-pane');
  const topbar = document.querySelector('.topbar');
  const archiveIsOverlay = window.innerWidth <= 1180;
  const readerIsOverlay = true;

  if (!archiveIsOverlay) archive.classList.remove('open');
  const archiveOpen = archiveIsOverlay && archive.classList.contains('open');
  const readerOpen = readerIsOverlay && reader.classList.contains('open');
  const archiveHidden = (archiveIsOverlay && !archiveOpen) || readerOpen;
  const archiveModalOpen = archiveOpen && !readerOpen;

  setAccessibleHidden(archive, archiveHidden);
  setAccessibleHidden(reader, readerIsOverlay && !readerOpen);
  setAccessibleHidden(feed, readerOpen || archiveModalOpen);
  setAccessibleHidden(topbar, readerOpen || archiveModalOpen);
  document.getElementById('nav-toggle').setAttribute('aria-expanded', String(archiveOpen));

  if (archiveModalOpen) {
    archive.setAttribute('role', 'dialog');
    archive.setAttribute('aria-modal', 'true');
  } else {
    archive.removeAttribute('role');
    archive.removeAttribute('aria-modal');
  }

  if (readerOpen) {
    reader.setAttribute('role', 'dialog');
    reader.setAttribute('aria-modal', 'true');
  } else {
    reader.removeAttribute('role');
    reader.removeAttribute('aria-modal');
  }
}

function toggleArchive(force) {
  const pane = document.getElementById('archive-pane');
  const wasOpen = pane.classList.contains('open');
  const open = typeof force === 'boolean' ? force : !pane.classList.contains('open');
  pane.classList.toggle('open', open);
  document.getElementById('nav-backdrop').classList.toggle('show', open);
  syncResponsivePaneState();
  if (open) pane.querySelector('a, button')?.focus();
  else if (wasOpen && window.innerWidth <= 1180) {
    document.getElementById('nav-toggle').focus({ preventScroll: true });
  }
}

function trapOverlayFocus(event, container) {
  const focusable = Array.from(container.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), [tabindex]:not([tabindex="-1"])'));
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

function openReader() {
  const reader = document.getElementById('reader-pane');
  toggleArchive(false);
  reader.classList.add('open');
  document.getElementById('reader-backdrop').classList.add('show');
  document.body.classList.add('reader-open');
  syncResponsivePaneState();
  (reader.querySelector('[data-close-reader]') || reader).focus({ preventScroll: true });
}

function closeReader() {
  const reader = document.getElementById('reader-pane');
  if (!reader.classList.contains('open')) return;
  reader.classList.remove('open');
  document.getElementById('reader-backdrop').classList.remove('show');
  document.body.classList.remove('reader-open');
  syncResponsivePaneState();
  UI.lastFeedTrigger?.focus({ preventScroll: true });
}

function bindEvents() {
  const search = document.getElementById('search-input');
  document.getElementById('nav-toggle').addEventListener('click', () => toggleArchive());
  document.getElementById('nav-close').addEventListener('click', () => toggleArchive(false));
  document.getElementById('nav-backdrop').addEventListener('click', () => toggleArchive(false));
  document.getElementById('reader-backdrop').addEventListener('click', closeReader);

  document.getElementById('archive-nav').addEventListener('click', event => {
    const topic = event.target.closest('[data-topic]');
    if (topic) {
      UI.topic = topic.dataset.topic;
      applyFeedFilter({ resetScroll: true });
      if (window.innerWidth <= 1180) toggleArchive(false);
      return;
    }
    if (event.target.closest('[data-view-id]') && window.innerWidth <= 1180) toggleArchive(false);
  });

  document.getElementById('topic-strip').addEventListener('click', event => {
    const button = event.target.closest('[data-topic]');
    if (!button) return;
    UI.topic = button.dataset.topic;
    applyFeedFilter({ resetScroll: true });
  });

  document.getElementById('feed-list').addEventListener('click', event => {
    if (event.target.closest('[data-retry-load]')) return location.reload();
    if (event.target.closest('[data-reset-feed]')) {
      UI.query = '';
      UI.topic = 'all';
      search.value = '';
      applyFeedFilter({ resetScroll: true });
      search.focus({ preventScroll: true });
      announce('Đã hiển thị toàn bộ bản tin');
      return;
    }
    const row = event.target.closest('[data-story-id]');
    if (!row) return;
    UI.lastFeedTrigger = row;
    selectStory(row.dataset.storyId);
    openReader();
  });

  document.getElementById('reader-pane').addEventListener('click', async event => {
    if (event.target.closest('[data-close-reader]')) return closeReader();
    const step = event.target.closest('[data-reader-step]');
    if (step) return stepStory(Number(step.dataset.readerStep), { restoreFocus: true });
    if (event.target.closest('[data-copy-story]')) {
      const copyButton = event.target.closest('[data-copy-story]');
      const copyButtonMarkup = copyButton.innerHTML;
      const item = UI.filteredItems.find(candidate => candidate.id === UI.selectedId);
      if (!item) return;
      const value = item.url || `${location.origin}${location.pathname}${location.hash}`;
      try {
        await navigator.clipboard.writeText(value);
        copyButton.classList.add('copied');
        copyButton.setAttribute('aria-label', 'Đã sao chép liên kết nguồn');
        copyButton.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg><span>Đã chép</span>';
        announce('Đã sao chép liên kết');
        setTimeout(() => {
          if (!copyButton.isConnected) return;
          copyButton.classList.remove('copied');
          copyButton.setAttribute('aria-label', 'Sao chép liên kết nguồn');
          copyButton.innerHTML = copyButtonMarkup;
        }, 1800);
      } catch (_) {
        copyButton.setAttribute('aria-label', 'Không thể sao chép liên kết');
        announce('Không thể sao chép liên kết');
      }
    }
  });

  search.addEventListener('input', () => {
    UI.query = search.value;
    applyFeedFilter({ resetScroll: true });
  });

  document.getElementById('mark-all-read').addEventListener('click', () => {
    UI.filteredItems.forEach(item => UI.readIds.add(item.id));
    persistReadIds();
    applyFeedFilter();
    announce(`Đã đánh dấu ${UI.filteredItems.length} tin là đã đọc`);
  });

  document.getElementById('theme-toggle').addEventListener('click', () => {
    setTheme(document.body.dataset.theme === 'dark' ? 'light' : 'dark');
  });

  window.addEventListener('hashchange', renderActiveView);
  window.addEventListener('resize', () => {
    if (window.innerWidth > 1180) toggleArchive(false);
    syncResponsivePaneState();
  });

  document.addEventListener('keydown', event => {
    const typing = /INPUT|TEXTAREA/.test(event.target.tagName) || event.target.isContentEditable;
    if (event.key === '/' && !typing) {
      event.preventDefault();
      search.focus();
    }
    if (event.key === 'Escape') {
      if (document.getElementById('reader-pane').classList.contains('open')) closeReader();
      else toggleArchive(false);
    }
    if (event.key === 'Tab') {
      const reader = document.getElementById('reader-pane');
      const archive = document.getElementById('archive-pane');
      if (reader.classList.contains('open')) trapOverlayFocus(event, reader);
      else if (archive.classList.contains('open') && window.innerWidth <= 1180) trapOverlayFocus(event, archive);
    }
    if (!typing && (event.key === 'j' || event.key === 'ArrowDown') && event.altKey) stepStory(1, { restoreFocus: true });
    if (!typing && (event.key === 'k' || event.key === 'ArrowUp') && event.altKey) stepStory(-1, { restoreFocus: true });
  });

  syncResponsivePaneState();
}

async function loadConfig() {
  try {
    const response = await fetch(`config.json?v=${Date.now()}`);
    if (!response.ok) return;
    CONFIG = await response.json();
    TOPICS = {};
    Object.values(CONFIG.topics || {}).forEach(topic => {
      if (topic.output_field) TOPICS[topic.output_field] = topic;
    });
    const site = CONFIG.site || {};
    if (site.title) {
      const title = stripLeadingSymbols(site.title);
      document.getElementById('site-title').textContent = title;
      document.title = title;
    }
  } catch (error) {
    console.warn('Không tải được config.json:', error);
  }
}

async function loadJson(path, required = false) {
  try {
    const response = await fetch(`${path}?v=${Date.now()}`);
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    if (required) throw new Error('Không thể kết nối tới dữ liệu bản tin.');
    console.warn(`Không tải được ${path}:`, error);
    return [];
  }
}

async function init() {
  const dateLabel = new Intl.DateTimeFormat('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit' }).format(new Date());
  document.getElementById('today-label').textContent = dateLabel.charAt(0).toUpperCase() + dateLabel.slice(1);
  let savedTheme = 'light';
  try { savedTheme = localStorage.getItem(THEME_STORE) || 'light'; } catch (_) {}
  setTheme(savedTheme);
  bindEvents();
  await loadConfig();

  const [daily, weekly, monthly] = await Promise.all([
    loadJson('cards.json', true), loadJson('weekly.json'), loadJson('monthly.json')
  ]);
  STATE = buildViews(daily, weekly, monthly);
  if (!location.hash && STATE.defaultId) history.replaceState(null, '', `#${STATE.defaultId}`);
  renderActiveView();
}

init().catch(error => {
  document.getElementById('archive-nav').setAttribute('aria-busy', 'false');
  const feed = document.getElementById('feed-list');
  feed.setAttribute('aria-busy', 'false');
  feed.innerHTML = emptyStateHtml('error', error.message);
  document.getElementById('feed-title').textContent = 'Bản tin tạm gián đoạn';
  document.getElementById('feed-summary').textContent = 'Thử tải lại để tiếp tục phiên đọc.';
  announce('Không tải được bản tin');
});
