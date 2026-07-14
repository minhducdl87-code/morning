// App bootstrap — global state, config.json load, ToC drawer toggle, hash-router init.
// Loaded last: by the time init() runs, date-week-utils.js/renderers.js/view-builder.js
// have already defined every function this file (and its dependents) call.

let TOPICS = {};   // { output_field: {emoji, label} } — loaded from config.json, see loadConfig()
let CONFIG = {};
let STATE = {views: [], byId: {}, currentWeek: '', monthlyByKey: {}, defaultId: ''};

// ── ToC drawer (theme is handled by puffer-theme.js external) ─────────────────

function toggleToc() {
  document.getElementById('toc').classList.toggle('open');
  document.getElementById('toc-backdrop').classList.toggle('show');
}

// ── Config + data load ─────────────────────────────────────────────────────────

async function loadConfig() {
  try {
    const r = await fetch('config.json?v='+Date.now());
    if (!r.ok) return;
    CONFIG = await r.json();
    TOPICS = {};
    for (const t of Object.values(CONFIG.topics || {})) {
      if (t.output_field) TOPICS[t.output_field] = t;
    }
    // Apply site branding from config
    const site = CONFIG.site || {};
    if (site.title) {
      const stripped = site.title.replace(/^\s*[\p{Emoji_Presentation}\p{Extended_Pictographic}]+\s*/u, '');
      const t = document.getElementById('site-title'); if (t) t.textContent = stripped || site.title;
      document.title = site.title;
    }
    if (site.logo) { const l = document.getElementById('site-logo'); if (l) l.textContent = site.logo; }
    if (site.footer) { const f = document.getElementById('site-footer'); if (f) f.textContent = site.footer; }
  } catch (e) {
    console.warn('config.json load failed:', e);
  }
}

async function init() {
  // ToC drawer toggle triggers (was inline onclick="toggleToc()" in markup)
  document.querySelectorAll('[data-toggle-toc]').forEach(el => el.addEventListener('click', toggleToc));

  // Keep <meta theme-color> in sync with the external light/dark toggle (puffer-theme.js)
  const syncThemeColor = () => {
    const m = document.querySelector('meta[name="theme-color"]');
    if (m) m.content = document.body.classList.contains('light') ? '#f0f7f4' : '#040d0a';
  };
  new MutationObserver(syncThemeColor).observe(document.body, { attributes: true, attributeFilter: ['class'] });
  syncThemeColor();

  await loadConfig();
  try {
    const [dailyRes, weeklyRes, monthlyRes] = await Promise.all([
      fetch('cards.json?v='+Date.now()),
      fetch('weekly.json?v='+Date.now()).catch(() => null),
      fetch('monthly.json?v='+Date.now()).catch(() => null),
    ]);
    const daily   = dailyRes.ok ? await dailyRes.json() : [];
    const weekly  = weeklyRes && weeklyRes.ok ? await weeklyRes.json() : [];
    const monthly = monthlyRes && monthlyRes.ok ? await monthlyRes.json() : [];

    document.getElementById('tagline').textContent = `${daily.length} ngày · ${weekly.length} tuần · ${monthly.length} tháng`;

    STATE = buildViews(daily, weekly, monthly);
    renderToc();
    renderActiveView();
    window.addEventListener('hashchange', renderActiveView);
  } catch (e) {
    document.getElementById('main').innerHTML = `<div class="error">Lỗi load dữ liệu 😅<br><small>${escapeHtml(e.message)}</small></div>`;
  }
}

init();
