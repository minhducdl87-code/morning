// Morning Digest — single-view rendering driven by ToC + URL hash router

const TAG_MAP = {hot:'tag-hot',api:'tag-api',feature:'tag-feature',deprecate:'tag-deprecate',model:'tag-model'};
const GAMING_TAG_MAP = {chart:'tag-chart',monet:'tag-monet',gameplay:'tag-gameplay','social-casino':'tag-social',casual:'tag-casual'};
const VERDICT_MAP = {yes:['verdict-yes','✅ YES'],maybe:['verdict-maybe','🤔 MAYBE'],skip:['verdict-skip','⏭️ SKIP']};
const MONTHS_VI = ['','Tháng 1','Tháng 2','Tháng 3','Tháng 4','Tháng 5','Tháng 6','Tháng 7','Tháng 8','Tháng 9','Tháng 10','Tháng 11','Tháng 12'];

let STATE = {views: [], byId: {}, currentWeek: '', monthlyByKey: {}, defaultId: ''};

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

// ── Theme + ToC drawer ────────────────────────────────────────────────────────

function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  document.documentElement.dataset.theme = saved;
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = saved === 'dark' ? '☀️' : '🌙';
}
function toggleTheme() {
  const curr = document.documentElement.dataset.theme || 'dark';
  const next = curr === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('theme', next);
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = next === 'dark' ? '☀️' : '🌙';
}
function toggleToc() {
  document.getElementById('toc').classList.toggle('open');
  document.getElementById('toc-backdrop').classList.toggle('show');
}

// ── Item renderers ────────────────────────────────────────────────────────────

function renderNewsItem(n) {
  const cls = TAG_MAP[(n.tag||'').split('|')[0]] || 'tag-api';
  const title = n.url
    ? `<a href="${n.url}" target="_blank" rel="noopener" class="news-title">${n.title}</a>`
    : `<span class="news-title">${n.title}</span>`;
  return `<div class="news-item"><div class="news-top">${title}<span class="tag ${cls}">${n.tagLabel||''}</span></div><p class="news-desc">${n.desc||''}</p>${n.source?`<div class="news-source">📅 ${n.source}</div>`:''}</div>`;
}
function renderGamingItem(n) {
  const cls = GAMING_TAG_MAP[(n.tag||'').split('|')[0]] || 'tag-gameplay';
  const title = n.url
    ? `<a href="${n.url}" target="_blank" rel="noopener" class="news-title">${n.title}</a>`
    : `<span class="news-title">${n.title}</span>`;
  return `<div class="news-item"><div class="news-top">${title}<span class="tag ${cls}">${n.tagLabel||''}</span></div><p class="news-desc">${n.desc||''}</p>${n.source?`<div class="news-source">📅 ${n.source}</div>`:''}</div>`;
}
function renderRepo(r) {
  const [cls,lbl] = VERDICT_MAP[r.verdict] || VERDICT_MAP.maybe;
  return `<div class="repo-card"><div class="repo-top"><a href="${r.url}" target="_blank" rel="noopener" class="repo-name">${r.name}</a><span class="repo-stars">⭐ ${r.stars||''}</span></div><p class="repo-desc">${r.desc||''}</p><div class="repo-verdict"><span class="verdict ${cls}">${lbl}</span><span class="verdict-reason">${r.reason||r.desc||''}</span></div></div>`;
}

// ── Card variant renderers (always open in single-view mode) ─────────────────

function dailyCardHtml(c) {
  const isToday = c.date === todayStr();
  const newsHtml = (c.news||[]).map(renderNewsItem).join('') || '<p class="muted-empty">Không có tin Claude hôm nay 😴</p>';
  const reposHtml = (c.repos||[]).length
    ? `<div class="section"><div class="section-title">🐙 GitHub Hot</div><div class="repo-grid">${c.repos.map(renderRepo).join('')}</div></div>`
    : '';
  const gamingHtml = (c.gamingNews||[]).length
    ? `<div class="section"><div class="section-title">🎮 Mobile Game</div>${c.gamingNews.map(renderGamingItem).join('')}</div>`
    : '';
  return `<div class="card${isToday?' is-today':''}" id="card-${c.date}">
    <div class="card-header">
      <div class="card-date-wrap">
        ${isToday?'<span class="card-badge-today">HÔM NAY</span>':''}
        <div><div class="card-day">${c.dayLabel||''}</div><div class="card-date-label">${c.dateLabel||c.date}</div></div>
      </div>
    </div>
    <div class="card-body open">
      <div class="section"><div class="section-title">🤖 Claude News</div>${newsHtml}</div>
      ${reposHtml}
      ${gamingHtml}
    </div>
  </div>`;
}

function weeklyCardHtml(w) {
  const highlights = (w.highlights||[]).map(renderNewsItem).join('') || '<p class="muted-empty">Chưa có highlight 🌙</p>';
  const repos = (w.topRepos||[]).length
    ? `<div class="section"><div class="section-title">🐙 Top Repos</div><div class="repo-grid">${w.topRepos.map(r=>renderRepo({...r,reason:r.desc||''})).join('')}</div></div>`
    : '';
  const gaming = (w.topGaming||[]).length
    ? `<div class="section"><div class="section-title">🎮 Top Gaming</div>${w.topGaming.map(renderGamingItem).join('')}</div>`
    : '';
  return `<div class="card" id="week-${w.fromDate}">
    <div class="card-header">
      <div class="card-date-wrap">
        <span class="card-badge-today card-badge-week">TUẦN</span>
        <div><div class="card-day">${w.weekLabel||''}</div><div class="card-date-label">${w.fromDate} → ${w.toDate}</div></div>
      </div>
    </div>
    <div class="card-body open">
      <div class="section"><div class="section-title">📰 Nổi bật tuần</div>${highlights}</div>
      ${repos}${gaming}
    </div>
  </div>`;
}

function monthlyCardHtml(m) {
  const news = (m.topNews||[]).map(renderNewsItem).join('') || '<p class="muted-empty">Không có tin nổi bật 🌙</p>';
  const repos = (m.topRepos||[]).length
    ? `<div class="section"><div class="section-title">🐙 Top Repos Tháng</div><div class="repo-grid">${m.topRepos.map(r=>renderRepo({...r,reason:r.reason||r.desc||''})).join('')}</div></div>`
    : '';
  const gaming = (m.topGaming||[]).length
    ? `<div class="section"><div class="section-title">🎮 Top Gaming Tháng</div>${m.topGaming.map(renderGamingItem).join('')}</div>`
    : '';
  return `<div class="card" id="month-${m.fromDate}">
    <div class="card-header">
      <div class="card-date-wrap">
        <span class="card-badge-today card-badge-month">THÁNG</span>
        <div><div class="card-day">${m.monthLabel||''}</div><div class="card-date-label">${m.fromDate} → ${m.toDate}</div></div>
      </div>
    </div>
    <div class="card-body open">
      <div class="section"><div class="section-title">📰 Tổng kết tháng</div>${news}</div>
      ${repos}${gaming}
    </div>
  </div>`;
}

// Group of daily cards within same month-week + optional weekly summary preface
function weekgroupHtml(view) {
  const summaryHtml = view.summary ? weeklyCardHtml(view.summary) : '';
  const cards = view.data.map(dailyCardHtml).join('');
  const hasContent = view.data.some(c => (c.news||[]).length || (c.repos||[]).length || (c.gamingNews||[]).length)
                  || (view.summary && ((view.summary.highlights||[]).length || (view.summary.topRepos||[]).length));
  const fallback = hasContent ? '' : renderEmptyFallback(view.monthKey);
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
                                          (v.data.news||[]).length || (v.data.repos||[]).length || (v.data.gamingNews||[]).length
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

async function init() {
  initTheme();
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
