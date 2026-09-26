(()=>{'use strict';
const host=document.getElementById('sale-trend'),table=document.getElementById('trend-rows'),metric=document.getElementById('trend-metric');
const records=window.PROJECT_DATA.records.filter(r=>r.phase==='成屋'&&r.use==='住家用'&&['2房','3房'].includes(r.rooms));
const fmt=x=>x.toLocaleString('zh-TW',{maximumFractionDigits:2});
function draw(){
 const key=metric.value,label=key==='unit'?'萬元／坪':'萬元（含車位）';
 const months=[...new Set(records.map(r=>r.date.slice(0,7)))].sort();
 const stamp=m=>Date.parse(m+'-01T00:00:00Z');
 const series=['2房','3房'].map((room,i)=>({room,color:i?'#b35a16':'#087f85',points:months.map(month=>{const rows=records.filter(r=>r.rooms===room&&r.date.startsWith(month)&&Number.isFinite(r[key]));return rows.length?{month,rows,value:rows.reduce((s,r)=>s+r[key],0)/rows.length}:null}).filter(Boolean)}));
 const max=Math.ceil(Math.max(...series.flatMap(s=>s.points.map(p=>p.value)))*1.15/5)*5;
 const x=m=>70+(stamp(m)-stamp(months[0]))/(stamp(months.at(-1))-stamp(months[0])||1)*730;
 const y=v=>280-v/max*230;
 let svg=`<svg viewBox="0 0 860 345" role="img" aria-label="和宜勝利成屋兩房與三房每月${key==='unit'?'平均單價':'平均總價'}走勢"><text x="70" y="23">${label}</text>`;
 for(let i=0;i<=4;i++){const v=max*i/4;svg+=`<line x1="70" x2="800" y1="${y(v)}" y2="${y(v)}" stroke="#dce5eb"/><text x="58" y="${y(v)+5}" text-anchor="end">${fmt(v)}</text>`}
 const ticks=[months[0],...['2023-01','2024-01','2025-01'].filter(m=>m>months[0]&&m<months.at(-1)),months.at(-1)];
 for(const m of ticks)svg+=`<text x="${x(m)}" y="310" text-anchor="middle">${m}</text>`;
 for(const s of series){svg+=`<polyline points="${s.points.map(p=>`${x(p.month)},${y(p.value)}`).join(' ')}" fill="none" stroke="${s.color}" stroke-width="2" stroke-dasharray="5 5"/>`;
  for(const p of s.points)svg+=`<circle cx="${x(p.month)}" cy="${y(p.value)}" r="6" fill="${s.color}" tabindex="0"><title>${p.month} ${s.room}：${fmt(p.value)} ${label}，${p.rows.length} 筆</title></circle>`;
 }
 svg+='</svg>';host.innerHTML=svg;
 table.innerHTML=months.map(m=>`<tr><td>${m}</td>${series.map(s=>{const p=s.points.find(p=>p.month===m);return `<td>${p?fmt(p.value):'—'}</td><td>${p?p.rows.length:'0'}</td>`}).join('')}</tr>`).join('');
 document.getElementById('trend-value-2').textContent='兩房'+(key==='unit'?'均價（萬／坪）':'均總價（萬）');
 document.getElementById('trend-value-3').textContent='三房'+(key==='unit'?'均價（萬／坪）':'均總價（萬）');
}
metric.addEventListener('change',draw);draw();
})();
