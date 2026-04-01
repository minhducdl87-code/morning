// Morning Digest — client-side rendering logic
// Handles: theme toggle, daily cards, gaming section, weekly digest tab

const TAG_MAP = {hot:'tag-hot',api:'tag-api',feature:'tag-feature',deprecate:'tag-deprecate',model:'tag-model'};
const GAMING_TAG_MAP = {chart:'tag-chart',monet:'tag-monet',gameplay:'tag-gameplay','social-casino':'tag-social',casual:'tag-casual'};
const VERDICT_MAP = {yes:['verdict-yes','✅ YES'],maybe:['verdict-maybe','🤔 MAYBE'],skip:['verdict-skip','⏭️ SKIP']};

// ── Helpers ──────────────────────────────────────────────────────────────────

function todayStr() { return new Date().toISOString().slice(0,10); }

// ── Theme Toggle ─────────────────────────────────────────────────────────────

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

// ── Render: Daily Cards ───────────────────────────────────────────────────────

function renderNewsItem(n) {
  const cls = TAG_MAP[(n.tag||'').split('|')[0]] || 'tag-api';
  const title = n.url
    ? `<a href="${n.url}" target="_blank" rel="noopener" class="news-title">${n.title}</a>`
    : `<span class="news-title">${n.title}</span>`;
  return `<div class="news-item"><div class="news-top">${title}<span class="tag ${cls}">${n.tagLabel}</span></div><p class="news-desc">${n.desc}</p>${n.source?`<div class="news-source">📅 ${n.source}</div>`:''}</div>`;
}

function renderRepo(r) {
  const [cls,lbl] = VERDICT_MAP[r.verdict] || VERDICT_MAP.maybe;
  return `<div class="repo-card"><div class="repo-top"><a href="${r.url}" target="_blank" rel="noopener" class="repo-name">${r.name}</a><span class="repo-stars">⭐ ${r.stars}</span></div><p class="repo-desc">${r.desc}</p><div class="repo-verdict"><span class="verdict ${cls}">${lbl}</span><span class="verdict-reason">${r.reason}</span></div></div>`;
}

function renderGamingItem(n) {
  const cls = GAMING_TAG_MAP[(n.tag||'').split('|')[0]] || 'tag-gameplay';
  const title = n.url
    ? `<a href="${n.url}" target="_blank" rel="noopener" class="news-title">${n.title}</a>`
    : `<span class="news-title">${n.title}</span>`;
  return `<div class="news-item"><div class="news-top">${title}<span class="tag ${cls}">${n.tagLabel}</span></div><p class="news-desc">${n.desc}</p>${n.source?`<div class="news-source">📅 ${n.source}</div>`:''}</div>`;
}

function renderCard(card, i) {
  const today = card.date === todayStr();
  const open  = i === 0;
  const gamingSection = (card.gamingNews && card.gamingNews.length)
    ? `<div class="section"><div class="section-title">🎮 Mobile Game</div>${card.gamingNews.map(renderGamingItem).join('')}</div>`
    : '';
  return `<div class="card" id="card-${card.date}">
    <div class="card-header" onclick="toggle('${card.date}')">
      <div class="card-date-wrap">
        ${today?'<span class="card-badge-today">HÔM NAY</span>':''}
        <div><div class="card-day">${card.dayLabel}</div><div class="card-date-label">${card.dateLabel}</div></div>
      </div>
      <button class="card-toggle-btn" id="tb-${card.date}">${open?'▲':'▼'}</button>
    </div>
    <div class="card-body${open?' open':''}" id="bd-${card.date}">
      <div class="section"><div class="section-title">🤖 Claude News</div>${(card.news||[]).map(renderNewsItem).join('')||'<p style="color:var(--text3);font-size:.82rem">Hôm nay Anthropic nghỉ ngơi 😴</p>'}</div>
      <div class="section"><div class="section-title">🐙 GitHub Hot</div><div class="repo-grid">${(card.repos||[]).map(renderRepo).join('')}</div></div>
      ${gamingSection}
    </div>
  </div>`;
}

function toggle(d) {
  const b = document.getElementById('bd-'+d), t = document.getElementById('tb-'+d);
  if (!b) return;
  const o = b.classList.toggle('open');
  t.textContent = o ? '▲' : '▼';
}

// ── Render: Weekly Cards ──────────────────────────────────────────────────────

function renderWeeklyCard(w, i) {
  const open = i === 0;
  const id   = `week-${w.fromDate}`;
  const gamingSection = (w.topGaming && w.topGaming.length)
    ? `<div class="section"><div class="section-title">🎮 Top Gaming</div>${w.topGaming.map(renderGamingItem).join('')}</div>`
    : '';
  const repoSection = (w.topRepos && w.topRepos.length)
    ? `<div class="section"><div class="section-title">🐙 Top Repos</div><div class="repo-grid">${w.topRepos.map(r=>renderRepo({...r,reason:r.desc})).join('')}</div></div>`
    : '';
  const highlights = (w.highlights||[]).map(renderNewsItem).join('') || '<p style="color:var(--text3);font-size:.82rem">Chưa có dữ liệu 🌙</p>';
  return `<div class="card" id="${id}">
    <div class="card-header" onclick="toggle('${id.replace('card-','')}')">
      <div class="card-date-wrap">
        ${i===0?'<span class="card-badge-today">MỚI NHẤT</span>':''}
        <div><div class="card-day">${w.weekLabel}</div><div class="card-date-label">${w.fromDate} → ${w.toDate}</div></div>
      </div>
      <button class="card-toggle-btn" id="tb-${id}">${open?'▲':'▼'}</button>
    </div>
    <div class="card-body${open?' open':''}" id="bd-${id}">
      <div class="section"><div class="section-title">📰 Nổi bật tuần</div>${highlights}</div>
      ${repoSection}
      ${gamingSection}
    </div>
  </div>`;
}

// ── View Switching ────────────────────────────────────────────────────────────

let weeklyLoaded = false;

function setView(v) {
  const daily  = document.getElementById('main');
  const weekly = document.getElementById('main-weekly');
  const dateNav = document.getElementById('date-nav');
  const btnD   = document.getElementById('btn-daily');
  const btnW   = document.getElementById('btn-weekly');

  if (v === 'weekly') {
    daily.style.display  = 'none';
    dateNav.style.display = 'none';
    weekly.style.display = 'block';
    btnD.classList.remove('active');
    btnW.classList.add('active');
    if (!weeklyLoaded) { weeklyLoaded = true; initWeekly(); }
  } else {
    daily.style.display  = 'block';
    dateNav.style.display = '';
    weekly.style.display = 'none';
    btnD.classList.add('active');
    btnW.classList.remove('active');
  }
}

async function initWeekly() {
  const el = document.getElementById('main-weekly');
  el.innerHTML = '<div class="loading">⏳ Đang tải...</div>';
  try {
    const r = await fetch('weekly.json?v='+Date.now());
    if (!r.ok) throw new Error('HTTP '+r.status);
    const weeklies = await r.json();
    if (!weeklies.length) { el.innerHTML = '<div class="empty">Chưa có tóm tắt tuần nào 🌙</div>'; return; }
    el.innerHTML = weeklies.map(renderWeeklyCard).join('');
  } catch(e) {
    el.innerHTML = `<div class="error">Lỗi load dữ liệu 😅<br><small>${e.message}</small></div>`;
  }
}

// ── Daily Init ────────────────────────────────────────────────────────────────

async function init() {
  try {
    const r = await fetch('cards.json?v='+Date.now());
    if (!r.ok) throw new Error('HTTP '+r.status);
    const cards = await r.json();
    if (!cards.length) { document.getElementById('main').innerHTML='<div class="empty">Chưa có bài nào 🌙</div>'; return; }
    document.getElementById('tagline').textContent = cards.length+' ngày gần nhất · tự động lúc 5AM';
    const nav = document.getElementById('date-nav');
    nav.innerHTML = cards.map(c=>`<a class="date-chip${c.date===todayStr()?' active':''}" href="#card-${c.date}">${c.dayLabel} ${c.dateLabel}</a>`).join('');
    document.getElementById('main').innerHTML = cards.map(renderCard).join('');
  } catch(e) {
    document.getElementById('main').innerHTML = `<div class="error">Lỗi load dữ liệu 😅<br><small>${e.message}</small></div>`;
  }
}

initTheme();
init();
