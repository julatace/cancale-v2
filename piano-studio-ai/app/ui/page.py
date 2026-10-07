PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Piano Studio AI</title>
<style>
:root{--bg:#f4f5f9;--card:#fff;--ink:#14162a;--mute:#6a6f8a;--line:#e3e5ef;--acc:#ffb703;--acc-ink:#2a1f00;--ok:#1a9d55;--bad:#d64045;--sel:#eef0ff;--selb:#5b61e6}
@media (prefers-color-scheme:dark){:root{--bg:#0d0f1e;--card:#171a2e;--ink:#eef0ff;--mute:#9aa0c0;--line:#272b47;--sel:#1f2450;--selb:#8d92ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:880px;margin:0 auto;padding:28px 16px 80px}
h1{font-size:28px;margin:0 0 4px}.sub{color:var(--mute);margin:0 0 26px}
h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:26px 0 10px}
.grid{display:grid;gap:12px}.g3{grid-template-columns:repeat(3,1fr)}.g2{grid-template-columns:repeat(2,1fr)}
@media(max-width:620px){.g3,.g2{grid-template-columns:1fr}}
.opt{background:var(--card);border:2px solid var(--line);border-radius:16px;padding:16px;text-align:left;cursor:pointer;color:inherit;font:inherit;transition:.12s}
.opt:hover{border-color:var(--selb)}.opt[aria-pressed=true]{background:var(--sel);border-color:var(--selb)}
.opt b{display:block;font-size:19px}.opt span{color:var(--mute);font-size:14px}
.shape{display:inline-block;border:2px solid currentColor;border-radius:6px;margin-bottom:8px;vertical-align:bottom}
.row{display:flex;flex-wrap:wrap;gap:18px;align-items:center;margin-top:14px;color:var(--mute)}
.row label{display:flex;gap:8px;align-items:center;cursor:pointer}
#go{width:100%;margin-top:22px;padding:18px;border:0;border-radius:16px;background:var(--acc);color:var(--acc-ink);font-size:20px;font-weight:700;cursor:pointer}
#go:disabled{opacity:.55;cursor:wait}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin-top:18px}
.chip{display:inline-block;padding:2px 10px;border-radius:99px;font-size:13px;font-weight:600;background:var(--sel);color:var(--selb)}
.chip.ok{background:#1a9d5522;color:var(--ok)}.chip.bad{background:#d6404522;color:var(--bad)}
#now{font-size:18px;font-weight:600;margin:8px 0}#log{max-height:240px;overflow:auto;font:13px/1.5 ui-monospace,Menlo,monospace;color:var(--mute);white-space:pre-wrap;margin:8px 0 0}
.bar{height:6px;border-radius:9px;background:var(--line);overflow:hidden;margin-top:8px}.bar i{display:block;height:100%;width:30%;background:var(--selb);animation:mv 1.3s infinite ease-in-out}
@keyframes mv{0%{margin-left:-30%}100%{margin-left:100%}}
.v{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px 0;border-top:1px solid var(--line)}.v:first-child{border-top:0}
.v small{color:var(--mute)}.v a,.v button{color:var(--selb);background:none;border:0;font:inherit;cursor:pointer;text-decoration:underline}
video{width:100%;max-height:70vh;border-radius:12px;background:#000;margin-top:12px}
</style></head><body><main>
<h1>Piano Studio AI</h1><p class="sub">Choisissez le niveau et le format, puis créez la vidéo. Tout le reste est automatique.</p>

<h2>1 · Niveau de difficulté</h2>
<div class="grid g3" id="levels"></div>
<h2>2 · Format de la vidéo</h2>
<div class="grid g2" id="formats"></div>
<div class="row">
  <label><input type="checkbox" id="publish"> Publier ensuite (YouTube si configuré)</label>
  <label>Nombre de vidéos <select id="count"><option>1</option><option>2</option><option>3</option></select></label>
</div>
<button id="go">Créer la vidéo</button>

<div class="panel" id="job" hidden>
  <span class="chip" id="chip">En cours</span>
  <div id="now">…</div><div class="bar" id="bar"><i></i></div>
  <pre id="log"></pre>
  <div id="result"></div>
</div>

<h2>Vidéos récentes</h2>
<div class="panel" id="vids"><small>Aucune pour l'instant.</small></div>
<div id="player"></div>

<script>
const $=s=>document.querySelector(s);let level=null,fmt=null,since=0,timer=null;
const api=(p,o)=>fetch(p,o).then(r=>r.json());
function shape(f){return `<i class="shape" style="width:${f.width>f.height?42:24}px;height:${f.width>f.height?24:42}px"></i>`}
function pick(box,val,set){box.querySelectorAll('.opt').forEach(b=>b.setAttribute('aria-pressed',b.dataset.k===val))}
api('/api/options').then(o=>{
  level=o.levels[1]?o.levels[1].key:o.levels[0].key;fmt=o.default_format;
  $('#levels').innerHTML=o.levels.map(l=>`<button class="opt" data-k="${l.key}"><b>${l.label}</b><span>${l.bpm} BPM · ${l.bpm<=80?'tempo lent, notes espacées':l.bpm<=100?'tempo modéré':'tempo rapide, plus dense'}</span></button>`).join('');
  $('#formats').innerHTML=o.formats.map(f=>`<button class="opt" data-k="${f.key}">${shape(f)}<b>${f.label}</b><span>${f.width}×${f.height} · ${f.long?'morceau entier, plusieurs minutes':'environ 1 minute'}</span></button>`).join('');
  $('#levels').onclick=e=>{const b=e.target.closest('.opt');if(b){level=b.dataset.k;pick($('#levels'),level)}};
  $('#formats').onclick=e=>{const b=e.target.closest('.opt');if(b){fmt=b.dataset.k;pick($('#formats'),fmt)}};
  pick($('#levels'),level);pick($('#formats'),fmt);
});
function esc(s){return String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function vids(){api('/api/videos').then(v=>{if(!v.length)return;$('#vids').innerHTML=v.map(x=>`<div class="v"><div><b>${esc(x.title)}</b><br><small>${esc(x.level)} · ${esc(x.format)} · ${x.duration}s · qualité ${x.quality??'-'}/100 · ${esc(x.status)} · ${esc(x.at)}</small></div>${x.file?`<button data-f="${esc(x.file)}">Voir</button>`:''}</div>`).join('')})}
$('#vids').onclick=e=>{const f=e.target.dataset.f;if(f){$('#player').innerHTML=`<video controls autoplay src="/files/${encodeURIComponent(f)}"></video>`;$('#player').scrollIntoView({behavior:'smooth'})}};
function poll(){api('/api/status?since='+since).then(s=>{
  since=s.last;const L=$('#log');if(s.logs.length){L.textContent+=s.logs.join('\n')+'\n';L.scrollTop=L.scrollHeight;$('#now').textContent=s.logs[s.logs.length-1]}
  const run=s.status==='running';$('#go').disabled=run;$('#bar').hidden=!run;
  $('#chip').textContent=run?'En cours':s.status==='done'?'Terminé':'Échec';$('#chip').className='chip '+(s.status==='done'?'ok':s.status==='failed'?'bad':'');
  if(!run){clearInterval(timer);timer=null;vids();
    if(s.status==='failed')$('#result').innerHTML=`<p>${esc(s.error)}</p>`;
    else if(s.result&&s.result.video){const r=s.result;$('#result').innerHTML=`<p>${r.status==='FAILED'?'La vidéo a échoué : '+esc(r.error||''):'Vidéo prête · qualité '+(r.qc?r.qc.score:'-')+'/100'}</p>`+(r.status!=='FAILED'?`<video controls src="/files/${encodeURIComponent(r.video.split('/').pop())}"></video>`:'')}}
})}
$('#go').onclick=()=>{
  $('#job').hidden=false;$('#log').textContent='';$('#result').innerHTML='';since=0;$('#now').textContent='Démarrage…';
  api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({level,format:fmt,publish:$('#publish').checked,count:+$('#count').value})})
   .then(r=>{if(r.error){$('#now').textContent=r.error;return}if(!timer)timer=setInterval(poll,1500);poll()})
};
vids();api('/api/status').then(s=>{if(s.status==='running'){$('#job').hidden=false;since=0;timer=setInterval(poll,1500);poll()}});
</script></main></body></html>
"""
