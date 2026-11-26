const $ = (id) => document.getElementById(id);
const fmt = (value) => value == null ? '—' : '$' + Number(value).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
async function request(path, body) {
  const response = await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,credentials:'same-origin'});
  const data = await response.json();
  if(!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
}
function esc(value){const node=document.createElement('span');node.textContent=String(value??'');return node.innerHTML;}
async function refresh(){try{
 const d=await request('/api/dashboard'); $('bot').textContent=d.state.status; $('lastRun').textContent=d.state.last_run?new Date(d.state.last_run).toLocaleString():'No run yet';
 $('equity').textContent=d.account?fmt(d.account.equity):'Unavailable'; $('cash').textContent=d.account?fmt(d.account.cash):'Unavailable'; $('accountLabel').textContent=d.demo?d.demo_label:'Connected paper account'; $('source').textContent=d.demo?'Illustrative demo':'Broker account'; $('positionCount').textContent=d.positions.length;
 $('signals').innerHTML=d.signals.length?d.signals.map(s=>`<tr><td>${esc(s.symbol)}</td><td><span class="signal ${esc(s.action)}">${esc(s.action.toUpperCase())}</span></td><td>${s.fast_sma==null?'—':fmt(s.fast_sma)}</td><td>${s.slow_sma==null?'—':fmt(s.slow_sma)}</td><td>${esc(s.reason)}</td></tr>`).join(''):'<tr><td colspan="5">Run analysis to generate signals</td></tr>';
 $('positions').innerHTML=d.positions.length?d.positions.map(p=>`<div class="limit"><strong>${esc(p.symbol)}</strong><span>${esc(p.qty)} shares · ${fmt(p.market_value)}</span></div>`).join(''):'<div class="empty">No open positions</div>';
 const orders=Array.isArray(d.orders)?d.orders:[]; $('orders').innerHTML=orders.length?orders.slice(0,10).map(o=>`<tr><td>${esc(o.symbol)}</td><td>${esc(o.side||'—')}</td><td>${esc(o.qty||o.quantity||'—')}</td><td>${esc(o.status)}</td><td>${esc(o.created_at||o.submitted_at||'—')}</td></tr>`).join(''):'<tr><td colspan="5">No orders yet</td></tr>';
 $('limits').innerHTML=Object.entries(d.limits).map(([k,v])=>`<div class="limit"><span>${esc(k.replaceAll('_',' '))}</span><strong>${esc(v)}</strong></div>`).join(''); $('audit').innerHTML=d.audit.map(a=>`<div class="event"><strong>${esc(a.event)}</strong><small>${esc(a.created_at)}</small></div>`).join('')||'<div class="empty">No events recorded</div>';
 if(d.state.last_error) show(d.state.last_error); else if(!$('notice').dataset.warning) $('notice').textContent='This educational dashboard does not provide investment advice. Strategy signals are not predictions.';
 }catch(e){show(e.message)}}
function show(message){$('notice').textContent=message;$('notice').dataset.warning='1';}
$('run').addEventListener('click',async()=>{try{const d=await request('/api/run',{submit_paper_orders:false,confirmed:false});show(`Analysis complete · ${d.signals.length} symbols checked. No orders submitted.`);await refresh()}catch(e){show(e.message)}});
$('pause').addEventListener('click',async()=>{try{const d=await request('/api/pause',{});$('pause').textContent=d.paused?'Resume':'Pause';await refresh()}catch(e){show(e.message)}});
$('stop').addEventListener('click',async()=>{if(!confirm('Emergency stop will prevent future analysis and paper order submissions. Continue?'))return;try{await request('/api/emergency-stop',{});show('Emergency stop is active. Restart the application to clear it.');await refresh()}catch(e){show(e.message)}});
refresh();setInterval(refresh,30000);
