// Morning Digest — hierarchical render: month → week → day, with sticky ToC

const TAG_MAP = {hot:'tag-hot',api:'tag-api',feature:'tag-feature',deprecate:'tag-deprecate',model:'tag-model'};
const GAMING_TAG_MAP = {chart:'tag-chart',monet:'tag-monet',gameplay:'tag-gameplay','social-casino':'tag-social',casual:'tag-casual'};
const VERDICT_MAP = {yes:['verdict-yes','✅ YES'],maybe:['verdict-maybe','🤔 MAYBE'],skip:['verdict-skip','⏭️ SKIP']};
const MONTHS_VI = ['','Tháng 1','Tháng 2','Tháng 3','Tháng 4','Tháng 5','Tháng 6','Tháng 7','Tháng 8','Tháng 9','Tháng 10','Tháng 11','Tháng 12'];

// ── Helpers ──────────────────────────────────────────────────────────────────

function todayStr() { return new Date().toISOString().slice(0,10); }

function monthKey(dateStr) {
  // "2026-05-10" → "2026-05"
  return dateStr.slice(0,7);
}

function monthLabelVi(key) {
  const [y,m] = key.split('-');
  return `${MONTHS_VI[parseInt(m,10)]}/${y}`;
}

function isoWeek(dateStr) {
  const d = new Date(dateStr+'T00:00:00');
  const dayNr = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - dayNr + 3);
  const firstThursday = d.valueOf();
  d.setUTCMonth(0, 1);
  if (d.getUTCDay() !== 4) d.setUTCMonth(0, 1 + ((4 - d.getUTCDay()) + 7) % 7);
  return 1 + Math.ceil((firstThursday - d) / 604800000);
}

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

function toggleToc() {
  document.getElementById('toc').classList.toggle('open');
  document.getElementById('toc-backdrop').classList.toggle('show');
}

// ── Render: shared item renderers ────────────────────────────────────────────

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
  return `<div class="repo-card"><div class="repo-top"><a href="${r.url}" target="_blank" rel="noopener" class="repo-name">${r.name}</a><span class="repo-stars">⭐ ${r.stars||''}</span></div><p class="repo-desc">${r.desc||''}</p><div class="repo-verdict"><span class="verdict ${cls}">${lbl}</span><span class="verdict-reason">${r.reason||''}</span></div></div>`;
}

function toggleCard(id) {
  const b = document.getElementById('bd-'+id), t = document.getElementById('tb-'+id);
  if (!b) return;
  const o = b.classList.toggle('open');
  if (t) t.textContent = o ? '▲' : '▼';
}

// ── Render: card variants ────────────────────────────────────────────────────

function renderDailyCard(c, opts) {
  const id = `card-${c.date}`;
  const open = !!opts.open;
  const isToday = c.date === todayStr();
  const newsHtml = (c.news||[]).map(renderNewsItem).join('') || '<p style="color:var(--text3);font-size:.82rem">Không có tin Claude hôm nay 😴</p>';
  const reposHtml = (c.repos||[]).length
    ? `<div class="section"><div class="section-title">🐙 GitHub Hot</div><div class="repo-grid">${c.repos.map(renderRepo).join('')}</div></div>`
    : '';
  const gamingHtml = (c.gamingNews||[]).length
    ? `<div class="section"><div class="section-title">🎮 Mobile Game</div>${c.gamingNews.map(renderGamingItem).join('')}</div>`
    : '';
  return `<div class="card${isToday?' is-today':''}" id="${id}">
    <div class="card-header" onclick="toggleCard('${c.date}')">
      <div class="card-date-wrap">
        ${isToday?'<span class="card-badge-today">HÔM NAY</span>':''}
        <div><div class="card-day">${c.dayLabel||''}</div><div class="card-date-label">${c.dateLabel||c.date}</div></div>
      </div>
      <button class="card-toggle-btn" id="tb-${c.date}">${open?'▲':'▼'}</button>
    </div>
    <div class="card-body${open?' open':''}" id="bd-${c.date}">
      <div class="section"><div class="section-title">🤖 Claude News</div>${newsHtml}</div>
      ${reposHtml}
      ${gamingHtml}
    </div>
  </div>`;
}

function renderWeeklyCard(w, opts) {
  const id = `week-${w.fromDate}`;
  const open = !!opts.open;
  const highlights = (w.highlights||[]).map(renderNewsItem).join('') || '<p style="color:var(--text3);font-size:.82rem">Chưa có highlight 🌙</p>';
  const repos = (w.topRepos||[]).length
    ? `<div class="section"><div class="section-title">🐙 Top Repos</div><div class="repo-grid">${w.topRepos.map(r=>renderRepo({...r,reason:r.desc||''})).join('')}</div></div>`
    : '';
  const gaming = (w.topGaming||[]).length
    ? `<div class="section"><div class="section-title">🎮 Top Gaming</div>${w.topGaming.map(renderGamingItem).join('')}</div>`
    : '';
  return `<div class="card" id="${id}">
    <div class="card-header" onclick="toggleCard('${id.replace('card-','')}')">
      <div class="card-date-wrap">
        <span class="card-badge-today card-badge-week">TUẦN</span>
        <div><div class="card-day">${w.weekLabel||''}</div><div class="card-date-label">${w.fromDate} → ${w.toDate}</div></div>
      </div>
      <button class="card-toggle-btn" id="tb-${id}">${open?'▲':'▼'}</button>
    </div>
    <div class="card-body${open?' open':''}" id="bd-${id}">
      <div class="section"><div class="section-title">📰 Nổi bật tuần</div>${highlights}</div>
      ${repos}
      ${gaming}
    </div>
  </div>`;
}

function renderMonthlyCard(m, opts) {
  const id = `month-${m.fromDate}`;
  const open = !!opts.open;
  const news = (m.topNews||[]).map(renderNewsItem).join('') || '<p style="color:var(--text3);font-size:.82rem">Không có tin nổi bật 🌙</p>';
  const repos = (m.topRepos||[]).length
    ? `<div class="section"><div class="section-title">🐙 Top Repos Tháng</div><div class="repo-grid">${m.topRepos.map(r=>renderRepo({...r,reason:r.reason||r.desc||''})).join('')}</div></div>`
    : '';
  const gaming = (m.topGaming||[]).length
    ? `<div class="section"><div class="section-title">🎮 Top Gaming Tháng</div>${m.topGaming.map(renderGamingItem).join('')}</div>`
    : '';
  return `<div class="card" id="${id}">
    <div class="card-header" onclick="toggleCard('${id.replace('card-','')}')">
      <div class="card-date-wrap">
        <span class="card-badge-today card-badge-month">THÁNG</span>
        <div><div class="card-day">${m.monthLabel||''}</div><div class="card-date-label">${m.fromDate} → ${m.toDate}</div></div>
      </div>
      <button class="card-toggle-btn" id="tb-${id}">${open?'▲':'▼'}</button>
    </div>
    <div class="card-body${open?' open':''}" id="bd-${id}">
      <div class="section"><div class="section-title">📰 Tổng kết tháng</div>${news}</div>
      ${repos}
      ${gaming}
    </div>
  </div>`;
}

// ── Group cards by month ─────────────────────────────────────────────────────

function buildHierarchy(daily, weekly, monthly) {
  // Determine current month (latest daily's month, fallback to today)
  const currentMonth = daily.length ? monthKey(daily[0].date) : monthKey(todayStr());

  // Group daily + weekly by month
  const byMonth = {};
  for (const d of daily) {
    const k = monthKey(d.date);
    (byMonth[k] = byMonth[k] || {daily:[], weekly:[], monthly:null}).daily.push(d);
  }
  for (const w of weekly) {
    const k = monthKey(w.toDate);
    (byMonth[k] = byMonth[k] || {daily:[], weekly:[], monthly:null}).weekly.push(w);
  }
  for (const m of monthly) {
    const k = monthKey(m.fromDate);
    (byMonth[k] = byMonth[k] || {daily:[], weekly:[], monthly:null}).monthly = m;
  }

  // Sorted month keys desc
  const keys = Object.keys(byMonth).sort().reverse();
  return {currentMonth, keys, byMonth};
}

// ── Render whole page + ToC ──────────────────────────────────────────────────

function renderPage(daily, weekly, monthly) {
  const {currentMonth, keys, byMonth} = buildHierarchy(daily, weekly, monthly);
  const main = document.getElementById('main');
  const tocBody = document.getElementById('toc-body');

  if (!keys.length) {
    main.innerHTML = '<div class="empty">Chưa có dữ liệu 🌙</div>';
    tocBody.innerHTML = '';
    return;
  }

  const sections = [];
  const tocEntries = [];
  let firstCardOpened = false;

  for (const key of keys) {
    const data = byMonth[key];
    const monthAnchor = `month-section-${key}`;
    const monthLabel = monthLabelVi(key);
    const isCurrent = key === currentMonth;

    const tocChildren = [];
    const items = [];

    if (isCurrent) {
      // Current month: show daily + weekly cards
      const sortedDaily = [...data.daily].sort((a,b) => b.date.localeCompare(a.date));
      for (const d of sortedDaily) {
        const open = !firstCardOpened;
        firstCardOpened = true;
        items.push(renderDailyCard(d, {open}));
        tocChildren.push({href:`#card-${d.date}`, label:`${d.dayLabel||''} ${d.dateLabel||d.date}`.trim()});
      }
      const sortedWeekly = [...data.weekly].sort((a,b) => b.fromDate.localeCompare(a.fromDate));
      for (const w of sortedWeekly) {
        items.push(renderWeeklyCard(w, {open:false}));
        tocChildren.push({href:`#week-${w.fromDate}`, label:`${w.weekLabel||'Tuần'} (${w.fromDate.slice(5)} → ${w.toDate.slice(5)})`});
      }
    } else if (data.monthly) {
      // Past month: show only monthly summary
      const open = !firstCardOpened;
      firstCardOpened = true;
      items.push(renderMonthlyCard(data.monthly, {open}));
      tocChildren.push({href:`#month-${data.monthly.fromDate}`, label:'Tổng kết tháng'});
    } else if (data.weekly.length) {
      // Past month with weeklies but no monthly summary yet — show weeklies
      const sortedWeekly = [...data.weekly].sort((a,b) => b.fromDate.localeCompare(a.fromDate));
      for (const w of sortedWeekly) {
        items.push(renderWeeklyCard(w, {open:false}));
        tocChildren.push({href:`#week-${w.fromDate}`, label:`${w.weekLabel||'Tuần'} (${w.fromDate.slice(5)} → ${w.toDate.slice(5)})`});
      }
    } else if (data.daily.length) {
      // Edge: past month still has dailies (rollup not yet run) — render them
      const sortedDaily = [...data.daily].sort((a,b) => b.date.localeCompare(a.date));
      for (const d of sortedDaily) {
        items.push(renderDailyCard(d, {open:false}));
        tocChildren.push({href:`#card-${d.date}`, label:`${d.dayLabel||''} ${d.dateLabel||d.date}`.trim()});
      }
    } else {
      continue;
    }

    sections.push(`<section class="month-section" id="${monthAnchor}">
      <h2 class="month-section-title">📅 ${monthLabel}${isCurrent?' <span class="meta">· current</span>':''}</h2>
      ${items.join('')}
    </section>`);
    tocEntries.push({key, monthAnchor, monthLabel, children:tocChildren});
  }

  main.innerHTML = sections.join('');

  // Build ToC
  tocBody.innerHTML = tocEntries.map(e =>
    `<div class="toc-month">
      <a class="toc-month-label" href="#${e.monthAnchor}">📅 ${e.monthLabel}</a>
      <ul class="toc-items">
        ${e.children.map(c => `<li><a class="toc-link" href="${c.href}">${c.label}</a></li>`).join('')}
      </ul>
    </div>`
  ).join('');

  // ToC active highlight via IntersectionObserver
  setupTocObserver();

  // Close drawer on ToC link click (mobile)
  tocBody.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      const toc = document.getElementById('toc');
      if (toc.classList.contains('open')) toggleToc();
    });
  });
}

function setupTocObserver() {
  const links = document.querySelectorAll('.toc-link, .toc-month-label');
  const targets = [...links].map(a => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  if (!targets.length) return;
  const linkByHash = {};
  links.forEach(a => linkByHash[a.getAttribute('href')] = a);

  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const link = linkByHash['#'+e.target.id];
        if (link) {
          links.forEach(l => l.classList.remove('active'));
          link.classList.add('active');
        }
      }
    });
  }, {rootMargin:'-100px 0px -60% 0px', threshold:0});

  targets.forEach(t => obs.observe(t));
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

    const days = daily.length;
    document.getElementById('tagline').textContent = `${days} ngày · ${weekly.length} tuần · ${monthly.length} tháng`;
    renderPage(daily, weekly, monthly);
  } catch (e) {
    document.getElementById('main').innerHTML = `<div class="error">Lỗi load dữ liệu 😅<br><small>${e.message}</small></div>`;
  }
}

init();
