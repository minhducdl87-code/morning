// Build view registry (weekgroups + monthly) and render ToC + active view (hash router).

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

// ── Render: ToC + active view ─────────────────────────────────────────────────

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
