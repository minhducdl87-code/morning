// Morning Digest — single-view rendering driven by ToC + URL hash router

const VERDICT_MAP = {yes:['verdict-yes','✅ YES'],maybe:['verdict-maybe','🤔 MAYBE'],skip:['verdict-skip','⏭️ SKIP']};
const MONTHS_VI = ['','Tháng 1','Tháng 2','Tháng 3','Tháng 4','Tháng 5','Tháng 6','Tháng 7','Tháng 8','Tháng 9','Tháng 10','Tháng 11','Tháng 12'];

// Loaded from config.json — see loadConfig()
let TOPICS = {};   // { output_field: {emoji, label} }
let CONFIG = {};

let STATE = {views: [], byId: {}, currentWeek: '', monthlyByKey: {}, defaultId: ''};

function tagClass(tag) {
  // Direct CSS class from tag name (all colors defined in index.html)
  return 'tag-' + (tag || 'api').split('|')[0].replace(/[^a-z0-9-]/gi,'').toLowerCase();
}

function sectionMeta(field) {
  const t = TOPICS[field];
  if (t) return {emoji: t.emoji || '•', label: t.section_label || field};
  // Fallback for historical fields
  const legacy = {
    news:{emoji:'🤖', label:'Claude News'},
    repos:{emoji:'🐙', label:'GitHub Hot'},
    gamingNews:{emoji:'🎮', label:'Mobile Game'},
    highlights:{emoji:'📰', label:'Nổi bật tuần'},
    topNews:{emoji:'📰', label:'Tổng kết tháng'},
    topRepos:{emoji:'🐙', label:'Top Repos'},
    topGaming:{emoji:'🎮', label:'Top Gaming'},
  };
  return legacy[field] || {emoji:'•', label: field.charAt(0).toUpperCase() + field.slice(1)};
}

// ── Date helpers ──────────────────────────────────────────────────────────────

function todayStr() { return new Date().toISOString().slice(0,10); }
function monthKey(s) { return s.slice(0,7); }
function monthLabelVi(key) { const [y,m]=key.split('-'); return `${MONTHS_VI[parseInt(m,10)]}/${y}`; }

// Custom week-of-month rule (Anh defined):
//   Tuần 1: ngày 1-7  | Tuần 2: 8-14  | Tuần 3: 15-21  | Tuần 4: 22-28  | Tuần 5: 29-end
function monthWeekKey(dateStr) {
  // "2026-05-10" → "2026-05-W2"
  const day = parseInt(dateStr.slice(8,10), 10);
  const w = Math.min(5, Math.floor((day - 1) / 7) + 1);
  return dateStr.slice(0,7) + '-W' + w;
}
function monthWeekRange(key) {
  // "2026-05-W2" → {from:"2026-05-08", to:"2026-05-14"}
  const ym = key.slice(0,7);
  const w  = parseInt(key.slice(-1), 10);
  const [year, month] = ym.split('-').map(Number);
  const lastDay  = new Date(year, month, 0).getDate();
  const startDay = (w - 1) * 7 + 1;
  const endDay   = (w === 5) ? lastDay : Math.min(w * 7, lastDay);
  const pad = n => String(n).padStart(2,'0');
  return {from: `${ym}-${pad(startDay)}`, to: `${ym}-${pad(endDay)}`};
}
function weekLabelText(key) {
  const r = monthWeekRange(key);
  const w = key.slice(-1);
  return `Tuần ${w} (${r.from.slice(8)}-${r.to.slice(8)}/${r.from.slice(5,7)})`;
}

// ── ToC drawer (theme is handled by puffer-theme.js external) ─────────────────

function toggleToc() {
  document.getElementById('toc').classList.toggle('open');
  document.getElementById('toc-backdrop').classList.toggle('show');
}

// ── Item renderers ────────────────────────────────────────────────────────────

function renderNewsItem(n) {
  const cls = tagClass(n.tag);
  const title = n.url
    ? `<a href="${n.url}" target="_blank" rel="noopener" class="news-title">${escapeHtml(n.title||'')}</a>`
    : `<span class="news-title">${escapeHtml(n.title||'')}</span>`;
  return `<div class="news-item"><div class="news-top">${title}<span class="tag ${cls}">${escapeHtml(n.tagLabel||'')}</span></div><p class="news-desc">${escapeHtml(n.desc||'')}</p>${n.source?`<div class="news-source">📅 ${escapeHtml(n.source)}</div>`:''}</div>`;
}
// Alias for legacy calls that used renderGamingItem
const renderGamingItem = renderNewsItem;
function renderRepo(r) {
  const [cls,lbl] = VERDICT_MAP[r.verdict] || VERDICT_MAP.maybe;
  return `<div class="repo-card"><div class="repo-top"><a href="${r.url}" target="_blank" rel="noopener" class="repo-name">${r.name}</a><span class="repo-stars">⭐ ${r.stars||''}</span></div><p class="repo-desc">${r.desc||''}</p><div class="repo-verdict"><span class="verdict ${cls}">${lbl}</span><span class="verdict-reason">${r.reason||r.desc||''}</span></div></div>`;
}

// ── Card variant renderers (always open in single-view mode) ─────────────────

function renderSection(field, arr) {
  if (!arr || !arr.length) return '';
  const {emoji, label} = sectionMeta(field);
  const isRepoField = arr[0] && arr[0].url && arr[0].url.startsWith('https://github.com/') && arr[0].name;
  const body = isRepoField
    ? `<div class="repo-grid">${arr.map(renderRepo).join('')}</div>`
    : arr.map(renderNewsItem).join('');
  return `<div class="section"><div class="section-title">${emoji} ${escapeHtml(label)}</div>${body}</div>`;
}

function listFields(card) {
  return Object.keys(card).filter(k => Array.isArray(card[k]) && !['date','dayLabel','dateLabel'].includes(k));
}

function dailyCardHtml(c) {
  const isToday = c.date === todayStr();
  const fields = listFields(c);
  const sections = fields.map(f => renderSection(f, c[f])).filter(Boolean).join('');
  const body = sections || '<p class="muted-empty">Không có tin hôm nay 😴</p>';
  return `<div class="card${isToday?' is-today':''}" id="card-${c.date}">
    <div class="card-header">
      <div class="card-date-wrap">
        ${isToday?'<span class="card-badge-today">HÔM NAY</span>':''}
        <div><div class="card-day">${escapeHtml(c.dayLabel||'')}</div><div class="card-date-label">${escapeHtml(c.dateLabel||c.date)}</div></div>
      </div>
    </div>
    <div class="card-body open">${body}</div>
  </div>`;
}

function weeklyCardHtml(w) {
  const fields = listFields(w);
  const sections = fields.map(f => renderSection(f, w[f])).filter(Boolean).join('');
  const body = sections || '<p class="muted-empty">Chưa có highlight 🌙</p>';
  return `<div class="card" id="week-${w.fromDate}">
    <div class="card-header">
      <div class="card-date-wrap">
        <span class="card-badge-today card-badge-week">TUẦN</span>
        <div><div class="card-day">${escapeHtml(w.weekLabel||'')}</div><div class="card-date-label">${w.fromDate} → ${w.toDate}</div></div>
      </div>
    </div>
    <div class="card-body open">${body}</div>
  </div>`;
}

function monthlyCardHtml(m) {
  const fields = listFields(m);
  const sections = fields.map(f => renderSection(f, m[f])).filter(Boolean).join('');
  const body = sections || '<p class="muted-empty">Không có tin nổi bật 🌙</p>';
  return `<div class="card" id="month-${m.fromDate}">
    <div class="card-header">
      <div class="card-date-wrap">
        <span class="card-badge-today card-badge-month">THÁNG</span>
        <div><div class="card-day">${escapeHtml(m.monthLabel||'')}</div><div class="card-date-label">${m.fromDate} → ${m.toDate}</div></div>
      </div>
    </div>
    <div class="card-body open">${body}</div>
  </div>`;
}

// Group of daily cards within same month-week + optional weekly summary preface
function weekgroupHtml(view) {
  const summaryHtml = view.summary ? weeklyCardHtml(view.summary) : '';
  const cards = view.data.map(dailyCardHtml).join('');
  const cardHasContent = view.data.some(c => listFields(c).some(f => (c[f]||[]).length));
  const summaryHasContent = view.summary && listFields(view.summary).some(f => (view.summary[f]||[]).length);
  const fallback = (cardHasContent || summaryHasContent) ? '' : renderEmptyFallback(view.monthKey);
  return summaryHtml + cards + fallback;
}

function renderEmptyFallback(currentMonthKey) {
  // Try monthly entry of current month → fallback to previous month
  const m = STATE.monthlyByKey[currentMonthKey];
  if (m && (m.topRepos||[]).length) {
    return `<div class="fallback-banner">📭 Tuần này chưa có tin — hiển thị repos hot ${m.monthLabel}:</div>${monthlyCardHtml(m)}`;
  }
  // Find most recent monthly
  const keys = Object.keys(STATE.monthlyByKey).sort().reverse();
  if (keys.length) {
    const fb = STATE.monthlyByKey[keys[0]];
    return `<div class="fallback-banner">📭 Chưa có tin tuần này — hiển thị ${fb.monthLabel}:</div>${monthlyCardHtml(fb)}`;
  }
  return '<div class="empty">📭 Chưa có dữ liệu nào</div>';
}

// ── Build view registry ───────────────────────────────────────────────────────

function buildViews(daily, weekly, monthly) {
  const views = [];
  const byId = {};

  // Group dailies by month-week key (custom rule)
  const weekGroups = {};
  for (const d of daily) {
    const wk = monthWeekKey(d.date);
    (weekGroups[wk] = weekGroups[wk] || []).push(d);
  }

  // Index weekly summaries by their fromDate's month-week key (drop ISO-week semantics)
  const weeklyByMW = {};
  for (const w of weekly||[]) {
    if (w.fromDate) weeklyByMW[monthWeekKey(w.fromDate)] = w;
  }

  // Determine current week key from latest daily, fallback to today
  const weekKeys = Object.keys(weekGroups).sort().reverse();
  const currentWeek = weekKeys[0] || monthWeekKey(todayStr());

  // Build weekgroup + individual daily views
  for (const wk of weekKeys) {
    const days = weekGroups[wk].sort((a,b) => b.date.localeCompare(a.date));
    const mKey = wk.slice(0,7);
    const id = `weekgroup-${wk}`;
    const view = {
      id, type:'weekgroup', data:days, monthKey:mKey, weekKey:wk,
      label: weekLabelText(wk),
      summary: weeklyByMW[wk] || null,
      isCurrent: wk === currentWeek,
    };
    views.push(view);
    byId[id] = view;
    for (const d of days) {
      const cid = `card-${d.date}`;
      const cv = {id:cid, type:'daily', data:d, monthKey:mKey, label:`${d.dayLabel||''} ${d.dateLabel||d.date}`.trim(), parentId:id};
      views.push(cv);
      byId[cid] = cv;
    }
  }

  // Monthly views (one per month)
  const monthlyByKey = {};
  for (const m of monthly||[]) {
    const id = `month-${m.fromDate}`;
    const v = {id, type:'monthly', data:m, monthKey:monthKey(m.fromDate), label:'Tổng kết tháng'};
    views.push(v); byId[id] = v;
    monthlyByKey[v.monthKey] = m;
  }

  const defaultId = byId[`weekgroup-${currentWeek}`] ? `weekgroup-${currentWeek}`
                  : (views[0] ? views[0].id : '');

  return {views, byId, currentWeek, monthlyByKey, defaultId};
}

// ── Render: main + ToC ────────────────────────────────────────────────────────

function renderToc() {
  const tocBody = document.getElementById('toc-body');
  // Group views by month
  const byMonth = {};
  for (const v of STATE.views) {
    if (v.type === 'daily') continue; // dailies shown under their weekgroup
    (byMonth[v.monthKey] = byMonth[v.monthKey] || []).push(v);
  }
  const keys = Object.keys(byMonth).sort().reverse();
  if (!keys.length) { tocBody.innerHTML = ''; return; }

  const html = keys.map(k => {
    const items = byMonth[k];
    const monthLbl = monthLabelVi(k);
    return `<div class="toc-month">
      <div class="toc-month-label">📅 ${monthLbl}</div>
      <ul class="toc-items">
        ${items.map(v => `<li><a class="toc-link" data-view="${v.id}" href="#${v.id}">${escapeHtml(v.label)}</a></li>`).join('')}
      </ul>
    </div>`;
  }).join('');
  tocBody.innerHTML = html;

  // Bind clicks
  tocBody.querySelectorAll('.toc-link').forEach(a => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      const id = a.dataset.view;
      navigate(id);
      if (window.innerWidth <= 900) toggleToc();
    });
  });
}

function escapeHtml(s) {
  return String(s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function navigate(viewId) {
  if (!STATE.byId[viewId]) viewId = STATE.defaultId;
  history.replaceState(null, '', '#' + viewId);
  renderActiveView();
}

function renderActiveView() {
  const hash = (location.hash || '').replace(/^#/, '');
  const id = STATE.byId[hash] ? hash : STATE.defaultId;
  const v = STATE.byId[id];
  const main = document.getElementById('main');
  if (!v) {
    main.innerHTML = '<div class="empty">📭 Chưa có dữ liệu</div>';
    return;
  }

  // Section title — month label + view label
  const monthLbl = monthLabelVi(v.monthKey);
  const subtitle = v.type === 'weekgroup' ? `${v.label}${v.isCurrent ? ' · current week' : ''}`
                : v.label;

  let body = '';
  if (v.type === 'weekgroup')      body = weekgroupHtml(v);
  else if (v.type === 'daily')     body = dailyCardHtml(v.data) + (
                                          listFields(v.data).some(f => (v.data[f]||[]).length)
                                          ? '' : renderEmptyFallback(v.monthKey));
  else if (v.type === 'weekly')    body = weeklyCardHtml(v.data);
  else if (v.type === 'monthly')   body = monthlyCardHtml(v.data);

  main.innerHTML = `<section class="month-section">
    <h2 class="month-section-title">📅 ${monthLbl} <span class="meta">· ${escapeHtml(subtitle)}</span></h2>
    ${body}
  </section>`;

  // Highlight active ToC link
  document.querySelectorAll('.toc-link').forEach(a => {
    a.classList.toggle('active', a.dataset.view === id || a.dataset.view === v.parentId);
  });

  window.scrollTo({top:0, behavior:'auto'});
}

// ── Init ──────────────────────────────────────────────────────────────────────

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
