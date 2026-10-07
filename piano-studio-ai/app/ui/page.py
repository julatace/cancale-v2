PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Piano Studio AI</title>
<style>
:root{
  --bg:#f3f4fa;--surface:#fff;--ink:#12142b;--mute:#667;--line:#e2e4f0;
  --brand:#5b5bf0;--brand-soft:#ecedff;--gold:#ffb703;--gold-ink:#2b1d00;
  --ok:#14915a;--bad:#d23b45;--shadow:0 1px 2px rgba(18,20,43,.06),0 8px 24px rgba(18,20,43,.06);
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0b0d1c;--surface:#151830;--ink:#eef0ff;--mute:#9ba1c4;--line:#262a4a;
  --brand:#8f8fff;--brand-soft:#212558;--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.35);}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Helvetica,Arial,sans-serif}
button,input,select{font:inherit;color:inherit}
:focus-visible{outline:3px solid var(--brand);outline-offset:2px}
.wrap{max-width:960px;margin:0 auto;padding:20px 16px 120px}
header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:22px}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:20px;letter-spacing:-.01em;margin-right:auto}
.logo svg{width:34px;height:34px}
.pill{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:99px;background:var(--surface);border:1px solid var(--line);font-size:13px;color:var(--mute)}
.pill b{color:var(--ink)}.dot{width:8px;height:8px;border-radius:50%;background:var(--mute)}.dot.on{background:var(--ok)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:20px;padding:22px;box-shadow:var(--shadow);margin-bottom:18px}
.step{display:flex;align-items:center;gap:10px;margin:0 0 14px}
.num{width:26px;height:26px;border-radius:50%;background:var(--brand);color:#fff;font-weight:700;font-size:14px;display:grid;place-items:center;flex:none}
.step h2{margin:0;font-size:18px}.step p{margin:0;color:var(--mute);font-size:14px}
.grid{display:grid;gap:12px}.g3{grid-template-columns:repeat(3,1fr)}.g2{grid-template-columns:repeat(2,1fr)}
@media(max-width:640px){.g3,.g2{grid-template-columns:1fr}}
.opt{position:relative;text-align:left;background:var(--surface);border:2px solid var(--line);border-radius:16px;padding:16px;cursor:pointer;transition:border-color .12s,background .12s,transform .06s}
.opt:hover{border-color:var(--brand)}.opt:active{transform:scale(.99)}
.opt[aria-checked=true]{border-color:var(--brand);background:var(--brand-soft)}
.opt .t{font-weight:700;font-size:18px;display:block}.opt .d{color:var(--mute);font-size:14px;display:block;margin-top:2px}
.bpm{font-size:30px;font-weight:800;letter-spacing:-.02em;margin-top:8px}.bpm small{font-size:13px;font-weight:600;color:var(--mute);margin-left:4px}
.meter{display:flex;gap:4px;margin-top:10px}.meter i{height:6px;flex:1;border-radius:9px;background:var(--line)}.meter i.on{background:var(--brand)}
.tick{position:absolute;right:14px;top:14px;width:24px;height:24px;border-radius:50%;border:2px solid var(--line);display:grid;place-items:center;color:transparent;font-size:14px;font-weight:800}
.opt[aria-checked=true] .tick{background:var(--brand);border-color:var(--brand);color:#fff}
.dev{display:flex;align-items:center;gap:14px}.dev svg{flex:none;color:var(--ink)}
.row{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-top:18px;padding-top:16px;border-top:1px solid var(--line)}
.sw{display:flex;align-items:center;gap:10px;cursor:pointer;color:var(--mute);font-size:15px}
.sw input{appearance:none;width:44px;height:26px;border-radius:99px;background:var(--line);position:relative;cursor:pointer;transition:.15s;flex:none}
.sw input::after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;transition:.15s;box-shadow:0 1px 3px rgba(0,0,0,.3)}
.sw input:checked{background:var(--brand)}.sw input:checked::after{left:21px}
.est{color:var(--mute);font-size:14px}
.cta{position:sticky;bottom:0;z-index:5;padding:26px 0 14px;background:linear-gradient(to top,var(--bg) 62%,transparent)}
#go{width:100%;border:0;border-radius:18px;padding:20px;background:var(--gold);color:var(--gold-ink);font-size:20px;font-weight:800;cursor:pointer;box-shadow:0 10px 30px rgba(255,183,3,.35);transition:transform .08s,filter .12s}
#go:hover:not(:disabled){filter:brightness(1.05)}#go:active:not(:disabled){transform:scale(.99)}
#go:disabled{background:var(--line);color:var(--mute);box-shadow:none;cursor:not-allowed}
.stepper{display:flex;gap:6px;margin:6px 0 14px;flex-wrap:wrap}
.stepper li{list-style:none;flex:1;min-width:92px;padding:8px 10px;border-radius:10px;background:var(--bg);color:var(--mute);font-size:13px;font-weight:600;text-align:center;border:1px solid var(--line)}
.stepper li.done{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:transparent}
.stepper li.cur{color:#fff;background:var(--brand);border-color:var(--brand)}
.stepper{padding:0;margin-left:0}
.now{font-size:18px;font-weight:700;margin:2px 0 10px}
.bar{height:6px;border-radius:9px;background:var(--line);overflow:hidden}.bar i{display:block;height:100%;width:30%;background:var(--brand);border-radius:9px;animation:mv 1.3s infinite ease-in-out}
@keyframes mv{0%{margin-left:-30%}100%{margin-left:100%}}
details{margin-top:12px;color:var(--mute);font-size:14px}summary{cursor:pointer}
#log{max-height:220px;overflow:auto;font:12.5px/1.55 ui-monospace,Menlo,monospace;white-space:pre-wrap;margin:8px 0 0}
.chip{display:inline-block;padding:3px 10px;border-radius:99px;font-size:13px;font-weight:700;background:var(--brand-soft);color:var(--brand)}
.chip.ok{background:color-mix(in srgb,var(--ok) 15%,transparent);color:var(--ok)}.chip.bad{background:color-mix(in srgb,var(--bad) 15%,transparent);color:var(--bad)}
.res{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));margin-top:16px}
.vid{background:var(--bg);border-radius:16px;padding:12px;border:1px solid var(--line)}
.vid video{width:100%;max-height:60vh;border-radius:10px;background:#000;display:block}
.vid .meta{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:0 0 8px;font-weight:700;font-size:15px}
.vid a{display:inline-block;margin-top:10px;color:var(--brand);font-weight:700;text-decoration:none}
.err{color:var(--bad);margin:8px 0 0;font-size:14px}
.hist .v{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px 0;border-top:1px solid var(--line)}.hist .v:first-child{border-top:0}
.hist small{color:var(--mute)}.hist button{background:var(--brand-soft);color:var(--brand);border:0;border-radius:10px;padding:8px 14px;font-weight:700;cursor:pointer}
.empty{color:var(--mute);margin:0}
[hidden]{display:none!important}
</style></head><body><div class="wrap">

<header>
  <div class="logo"><svg viewBox="0 0 34 34" aria-hidden="true"><rect width="34" height="34" rx="9" fill="#5b5bf0"/><g fill="#fff"><rect x="6" y="7" width="4.4" height="20" rx="1"/><rect x="12" y="7" width="4.4" height="20" rx="1"/><rect x="18" y="7" width="4.4" height="20" rx="1"/><rect x="24" y="7" width="4.4" height="20" rx="1"/></g><g fill="#ffb703"><rect x="9" y="7" width="3.6" height="12" rx="1"/><rect x="21" y="7" width="3.6" height="12" rx="1"/></g></svg>Piano Studio AI</div>
  <span class="pill" title="Morceaux déjà téléchargés et vérifiés"><span class="dot" id="sdot"></span>Réserve : <b id="stock">…</b></span>
  <span class="pill" id="engine" title="Moteur utilisé pour fabriquer la vidéo">Moteur : <b>…</b></span>
</header>

<section class="card">
  <div class="step"><span class="num">1</span><div><h2>Niveau de difficulté</h2><p>Plus le tempo est rapide, plus c'est difficile à jouer.</p></div></div>
  <div class="grid g3" id="levels" role="radiogroup" aria-label="Niveau"></div>

  <div class="step" style="margin-top:26px"><span class="num">2</span><div><h2>Formats</h2><p>Les deux sont créés d'office avec le même morceau. Décochez-en un si besoin.</p></div></div>
  <div class="grid g2" id="formats" aria-label="Formats"></div>

  <div class="row">
    <label class="sw"><input type="checkbox" id="publish"> Publier ensuite (YouTube si configuré)</label>
    <span class="est" id="est"></span>
  </div>
</section>

<div class="cta"><button id="go">Créer</button></div>

<section class="card" id="job" hidden style="margin-top:18px">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><b>Création en cours</b><span class="chip" id="chip">En cours</span></div>
  <ol class="stepper" id="stepper"></ol>
  <div class="now" id="now">…</div>
  <div class="bar" id="bar"><i></i></div>
  <p class="err" id="err" hidden></p>
  <details><summary>Détails techniques</summary><pre id="log"></pre></details>
  <div class="res" id="res"></div>
</section>

<section class="card hist">
  <div class="step"><div><h2>Vidéos récentes</h2></div></div>
  <div id="vids"><p class="empty">Aucune vidéo pour l'instant.</p></div>
  <div id="player"></div>
</section>

<script>
const $=s=>document.querySelector(s);
let level=null,formats=new Set(),since=0,timer=null,opts=null,cur=-1,fmtLabel='';
const api=(p,o)=>fetch(p,o).then(r=>r.json());
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const STEPS=['Morceau','Passage','Fabrication','Qualité','Publication'];
const dev=f=>f.width>f.height
  ?'<svg width="64" height="40" viewBox="0 0 64 40" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="3" width="58" height="34" rx="6"/><path d="M12 28h40" stroke-width="5" stroke-linecap="round" opacity=".35"/></svg>'
  :'<svg width="40" height="64" viewBox="0 0 40 64" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="3" width="34" height="58" rx="7"/><path d="M12 52h16" stroke-width="5" stroke-linecap="round" opacity=".35"/></svg>';
const estimate=()=>{const n=formats.size;$('#est').textContent=n?`Environ ${[...formats].some(k=>opts.formats.find(f=>f.key===k).long)?'6 à 8':'2 à 3'} minutes${n>1?' pour les deux vidéos':''}`:'Choisissez au moins un format';
  $('#go').disabled=!n||!level;$('#go').textContent=n>1?'Créer les 2 vidéos':n===1?'Créer la vidéo':'Choisissez un format'};
function render(){
  $('#levels').innerHTML=opts.levels.map((l,i)=>`<button class="opt" role="radio" aria-checked="${l.key===level}" data-k="${l.key}"><span class="tick">✓</span><span class="t">${esc(l.label)}</span><span class="bpm">${l.bpm}<small>BPM</small></span><span class="meter">${[0,1,2].map(j=>`<i class="${j<=i?'on':''}"></i>`).join('')}</span></button>`).join('');
  $('#formats').innerHTML=opts.formats.map(f=>`<button class="opt dev" role="checkbox" aria-checked="${formats.has(f.key)}" data-k="${f.key}"><span class="tick">✓</span>${dev(f)}<span><span class="t">${esc(f.label.split(' (')[0])}</span><span class="d">${esc((f.label.match(/\(([^)]+)\)/)||[,''])[1])}</span><span class="d">${f.width}×${f.height} · ${f.long?'morceau entier (jusqu\'à 5 min)':'environ 1 minute'}</span></span></button>`).join('');
  estimate()}
$('#levels').onclick=e=>{const b=e.target.closest('.opt');if(b){level=b.dataset.k;render()}};
$('#formats').onclick=e=>{const b=e.target.closest('.opt');if(!b)return;const k=b.dataset.k;formats.has(k)?formats.delete(k):formats.add(k);render()};
function info(){api('/api/info').then(i=>{$('#stock').textContent=`${i.stock} morceau${i.stock>1?'x':''} d'avance`;$('#sdot').className='dot'+(i.stock>0?' on':'');
  $('#engine').innerHTML=`Moteur : <b>${i.engine==='synthesia'?'Synthesia':'rendu intégré'}</b>`;$('#engine').title=i.engine==='synthesia'?'Votre application Synthesia pilotée automatiquement':'Synthesia non prêt : rendu intégré utilisé'})}
function vids(){api('/api/videos').then(v=>{if(!v.length)return;$('#vids').innerHTML=v.map(x=>`<div class="v"><div><b>${esc(x.title)}</b><br><small>${esc(x.level)} · ${esc(x.format)} · ${x.duration}s · qualité ${x.quality??'-'}/100 · ${esc(x.status)} · ${esc(x.at)}</small></div>${x.file?`<button data-f="${esc(x.file)}">Voir</button>`:''}</div>`).join('')})}
$('#vids').onclick=e=>{const f=e.target.dataset.f;if(f){$('#player').innerHTML=`<video controls autoplay playsinline style="width:100%;max-height:70vh;border-radius:12px;background:#000;margin-top:12px" src="/files/${encodeURIComponent(f)}"></video>`;$('#player').scrollIntoView({behavior:'smooth',block:'center'})}};
function stepper(){$('#stepper').innerHTML=STEPS.map((s,i)=>`<li class="${i<cur?'done':i===cur?'cur':''}">${i<cur?'✓ ':''}${s}</li>`).join('')}
function track(line){const m=line.match(/\[(vertical|horizontal)\]/);if(m)fmtLabel=m[1]==='vertical'?'Vertical':'Horizontal';
  const k=line.startsWith('♪')?0:/^[🔎✂]/u.test(line)?1:line.startsWith('🎬')?2:line.startsWith('✔')?3:line.startsWith('📤')?4:null;
  if(line.startsWith('✂'))cur=1;else if(k!==null&&k>cur)cur=k}
function results(r){const list=r.videos||[r];$('#res').innerHTML=list.filter(x=>x&&x.video).map(x=>{const f=x.video.split('/').pop(),bad=x.status==='FAILED';
  return `<div class="vid"><div class="meta"><span>${x.format==='horizontal'?'Horizontal long':'Vertical court'}</span><span class="chip ${bad?'bad':'ok'}">${bad?'Échec':'Qualité '+(x.qc?x.qc.score:'-')+'/100'}</span></div>${bad?`<p class="err">${esc(x.error||'La fabrication a échoué')}</p>`:`<video controls playsinline preload="metadata" src="/files/${encodeURIComponent(f)}"></video><a href="/files/${encodeURIComponent(f)}" download="${esc(f)}">⬇ Télécharger</a>`}</div>`}).join('')}
function poll(){api('/api/status?since='+since).then(s=>{
  since=s.last;const L=$('#log');s.logs.forEach(l=>track(l));
  if(s.logs.length){L.textContent+=s.logs.join('\n')+'\n';L.scrollTop=L.scrollHeight;const last=s.logs[s.logs.length-1];$('#now').textContent=(fmtLabel&&s.status==='running'?fmtLabel+' · ':'')+last.replace(/\s*\[(vertical|horizontal)\]\s*/,' ').trim()}
  stepper();const run=s.status==='running';$('#bar').hidden=!run;estimate();if(run){$('#go').disabled=true;$('#go').textContent='Création en cours…'}
  $('#chip').textContent=run?'En cours':s.status==='done'?'Terminé':'Échec';$('#chip').className='chip '+(s.status==='done'?'ok':s.status==='failed'?'bad':'');
  if(!run){clearInterval(timer);timer=null;vids();info();cur=s.status==='done'?5:cur;stepper();
    if(s.status==='failed'){$('#err').hidden=false;$('#err').textContent=s.error}
    else if(s.result){$('#now').textContent='Terminé';results(Array.isArray(s.result)?{videos:s.result.flatMap(r=>r.videos||[r])}:s.result)}}
})}
$('#go').onclick=()=>{
  $('#job').hidden=false;$('#log').textContent='';$('#res').innerHTML='';$('#err').hidden=true;since=0;cur=-1;fmtLabel='';stepper();$('#now').textContent='Démarrage…';
  $('#job').scrollIntoView({behavior:'smooth',block:'start'});
  api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({level,formats:[...formats],publish:$('#publish').checked})})
   .then(r=>{if(r.error){$('#now').textContent=r.error;return}if(!timer)timer=setInterval(poll,1500);poll()})};
api('/api/options').then(o=>{opts=o;level=(o.levels[1]||o.levels[0]).key;formats=new Set(o.default_formats);render()});
info();vids();setInterval(info,20000);
api('/api/status').then(s=>{if(s.status==='running'){$('#job').hidden=false;since=0;timer=setInterval(poll,1500);poll()}});
</script></div></body></html>
"""
