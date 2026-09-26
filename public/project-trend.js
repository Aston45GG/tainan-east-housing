(()=>{'use strict';
const host=document.getElementById('project-trends'),metric=document.getElementById('project-trend-metric');
const records=window.PROJECT_DATA.records.filter(r=>['兩房','三房'].includes(r.rooms));
const groups=[{name:'E 棟',towers:['E棟']},{name:'F／G 棟',towers:['F棟','G棟']},{name:'H／I／J／K 棟',towers:['H棟','I棟','J棟','K棟']}];
const dates=records.map(r=>r.date.slice(0,7)).sort(),months=[];
for(let d=new Date(dates[0]+'-01T00:00:00Z');d.toISOString().slice(0,7)<=dates.at(-1);d.setUTCMonth(d.getUTCMonth()+1))months.push(d.toISOString().slice(0,7));
const fmt=x=>x.toLocaleString('zh-TW',{maximumFractionDigits:2});
function draw(){
 const key=metric.value,label=key==='unit'?'平均單價（萬元／坪）':'平均總價（萬元，含車位）';
 const categories=[
  {room:'兩房',name:'兩房 · 6 樓以下（含 6 樓）',color:'#087f85',dash:'',accept:r=>r.floor<=6},
  {room:'兩房',name:'兩房 · 7 樓以上',color:'#2563eb',dash:'6 4',accept:r=>r.floor>=7},
  {room:'三房',name:'三房 · 6 樓以下（含 6 樓）',color:'#b35a16',dash:'',accept:r=>r.floor<=6},
  {room:'三房',name:'三房 · 7 樓以上',color:'#9333b8',dash:'6 4',accept:r=>r.floor>=7}
 ];
 const sets=groups.map(g=>({...g,series:categories.map(c=>({...c,points:months.map(month=>{
  const rows=records.filter(r=>g.towers.includes(r.tower)&&c.accept(r)&&r.rooms===c.room&&r.date.startsWith(month)&&Number.isFinite(r[key]));
  return rows.length?{month,n:rows.length,value:rows.reduce((s,r)=>s+r[key],0)/rows.length}:null;
 })}))}));
 const values=sets.flatMap(g=>g.series.flatMap(s=>s.points.filter(Boolean).map(p=>p.value)));
 const step=key==='unit'?5:500,min=key==='unit'?Math.floor((Math.min(...values)-1)/step)*step:0,max=Math.ceil((Math.max(...values)+(key==='unit'?1:0))/step)*step;
 const x=i=>70+i/(months.length-1||1)*730,y=v=>280-(v-min)/(max-min)*230;
 host.innerHTML=sets.map(g=>{
  let svg=`<svg viewBox="0 0 860 350" role="img" aria-label="國城寶實 ${g.name} 兩房與三房逐月${label}"><text x="70" y="23">${label}</text>`;
  for(let i=0;i<=4;i++){const v=min+(max-min)*i/4;svg+=`<line x1="70" x2="800" y1="${y(v)}" y2="${y(v)}" stroke="#dce5eb"/><text x="58" y="${y(v)+5}" text-anchor="end">${fmt(v)}</text>`;}
  months.forEach((m,i)=>{svg+=`<text x="${x(i)}" y="310" text-anchor="end" transform="rotate(-35 ${x(i)} 310)">${m}</text>`;});
  for(const s of g.series){let segment=[];const flush=()=>{if(segment.length>1)svg+=`<polyline points="${segment.join(' ')}" fill="none" stroke="${s.color}" stroke-width="2" stroke-dasharray="${s.dash}"/>`;segment=[];};
   s.points.forEach((p,i)=>{if(!p){flush();return;}segment.push(`${x(i)},${y(p.value)}`);});flush();
   s.points.forEach((p,i)=>{if(p)svg+=`<circle cx="${x(i)}" cy="${y(p.value)}" r="5" fill="${s.color}" tabindex="0"><title>${p.month} ${s.name}：${fmt(p.value)}，${p.n} 筆</title></circle>`;});
  }
  svg+='</svg>';
  const rows=months.map((m,i)=>`<tr><td>${m}</td>${g.series.map(s=>{const p=s.points[i];return `<td>${p?fmt(p.value):'—'}</td><td>${p?p.n:0}</td>`;}).join('')}</tr>`).join('');
  return `<section class="panel"><h3>${g.name}</h3><p class="hint">${key==='unit'?'縱軸未從 0 起算；所有分組使用相同刻度。':'總價含車位；所有分組使用相同刻度。'}</p><div class="trend-key" style="display:flex;flex-wrap:wrap;gap:12px 24px">${g.series.map(s=>`<span style="color:${s.color}">${s.dash?'┄':'━'} ${s.name}</span>`).join('')}</div><div class="sale-trend">${svg}</div><details><summary>查看逐月數值與樣本數</summary><div class="table-wrap"><table><thead><tr><th>交易月份</th>${g.series.map(s=>`<th>${s.name}<br>${label}</th><th>筆數</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div></details></section>`;
 }).join('');
}
metric.addEventListener('change',draw);draw();
})();
