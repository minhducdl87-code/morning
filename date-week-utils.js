// Date / week-of-month helpers — no deps, loaded first.

const MONTHS_VI = ['','Tháng 1','Tháng 2','Tháng 3','Tháng 4','Tháng 5','Tháng 6','Tháng 7','Tháng 8','Tháng 9','Tháng 10','Tháng 11','Tháng 12'];

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
