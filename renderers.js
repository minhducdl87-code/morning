// Card / item HTML renderers (pure string builders).
// Reads TOPICS/STATE globals declared in router-init.js — safe because these
// functions only run after all scripts are loaded (init() call), not at parse time.

const VERDICT_MAP = {yes:['verdict-yes','✅ YES'],maybe:['verdict-maybe','🤔 MAYBE'],skip:['verdict-skip','⏭️ SKIP']};

function tagClass(tag) {
  // Direct CSS class from tag name (all colors defined in styles.css)
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

function escapeHtml(s) {
  return String(s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── Item renderers ────────────────────────────────────────────────────────────

function renderNewsItem(n) {
  const cls = tagClass(n.tag);
  const newBadge = n.addedEvening ? '<span class="badge-new" title="Cập nhật tối">🆕</span>' : '';
  const title = n.url
    ? `<a href="${n.url}" target="_blank" rel="noopener" class="news-title">${escapeHtml(n.title||'')}</a>${newBadge}`
    : `<span class="news-title">${escapeHtml(n.title||'')}</span>${newBadge}`;
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
