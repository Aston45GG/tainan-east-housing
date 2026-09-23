function monthlyTopThree(records) {
  const groups = new Map();
  for (const r of records) {
    if (!Number.isFinite(r.unit) || r.unit <= 0) continue;
    if (!groups.has(r.month)) groups.set(r.month, []);
    groups.get(r.month).push(r);
  }
  return new Map([...groups].sort(([a], [b]) => b.localeCompare(a)).map(([month, rows]) => [month,
    rows.slice().sort((a, b) => b.unit - a.unit || b.date.localeCompare(a.date) || a.id.localeCompare(b.id)).slice(0, 3)
  ]));
}

function renderRanking(records) {
  const groups = monthlyTopThree(records);
  const selected = document.getElementById('month').value;
  const months = selected ? [selected] : [...new Set(data.records.map(r => r.month))].sort().reverse();
  document.getElementById('ranking').innerHTML = months.map(month => {
    const rows = groups.get(month) || [];
    return `<section class="ranking-month" aria-label="${esc(month)} 單坪前三名"><h3>${esc(month)}<small>${rows.length ? `最高 ${fmt(rows[0].unit, 2)} 萬／坪` : '無符合條件的單價'}</small></h3>${rows.length ? `<ol class="ranking-list">${rows.map((r, i) => `<li><span class="rank-number">${i + 1}</span><div class="rank-property"><strong>${esc(r.address)}</strong><p>${esc(r.date)} · ${esc(r.type)} · ${esc(r.floor)}</p><p>總價 ${fmt(r.total, 0)} 萬 · ${fmt(r.area)} 坪${r.age == null ? '' : ` · 屋齡 ${fmt(r.age)} 年`}</p>${r.note ? `<p class="rank-note">${esc(r.note)}</p>` : ''}${r.parkingUnclear ? '<p class="rank-note">車位價格或面積未分列</p>' : ''}</div><div class="rank-price"><strong>${fmt(r.unit, 2)}</strong><span>萬／坪</span></div></li>`).join('')}</ol>${rows.length < 3 ? '<p class="hint">本月符合條件且有單價的案件不足三筆。</p>' : ''}` : '<p class="empty">本月沒有符合條件且有單價的成交。</p>'}</section>`;
  }).join('') || '<p class="empty">尚無可供排名的成交資料。</p>';
}

if (typeof module !== 'undefined') module.exports = { monthlyTopThree };
