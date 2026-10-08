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
.stop{background:var(--bad);color:#fff;border:0;border-radius:10px;padding:8px 16px;font-weight:700;cursor:pointer}.stop.ghost{background:transparent;color:var(--bad);border:2px solid var(--bad)}
.stop:disabled{opacity:.6;cursor:wait}
.err{color:var(--bad);margin:8px 0 0;font-size:14px}
.hist .v{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px 0;border-top:1px solid var(--line)}.hist .v:first-child{border-top:0}
.hist small{color:var(--mute)}.hist button{background:var(--brand-soft);color:var(--brand);border:0;border-radius:10px;padding:8px 14px;font-weight:700;cursor:pointer}
.empty{color:var(--mute);margin:0}
.drop{border:2px dashed var(--line);border-radius:16px;padding:18px;text-align:center;color:var(--mute);cursor:pointer;transition:.12s;margin-top:12px}
.drop:hover,.drop.over{border-color:var(--brand);background:var(--brand-soft);color:var(--ink)}
.drop b{display:block;color:var(--ink);font-size:16px}
.rights{display:flex;gap:10px;align-items:flex-start;margin-top:10px;font-size:14px;color:var(--mute);cursor:pointer}
.rights input{margin-top:4px;width:18px;height:18px;flex:none}
.songs{display:grid;gap:8px;margin-top:4px;max-height:260px;overflow:auto}
.song{display:flex;align-items:center;gap:12px;padding:10px 14px;border:2px solid var(--line);border-radius:12px;cursor:pointer;background:var(--surface);text-align:left;width:100%}
.song[aria-checked=true]{border-color:var(--brand);background:var(--brand-soft)}
.song .n{flex:1;min-width:0}.song .n b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.song .n small{color:var(--mute)}
.tag{font-size:12px;font-weight:700;padding:2px 8px;border-radius:99px;background:var(--bg);color:var(--mute);border:1px solid var(--line)}
.tag.mine{background:var(--brand-soft);color:var(--brand);border-color:transparent}
.x{background:none;border:0;color:var(--mute);cursor:pointer;font-size:18px;padding:2px 8px;border-radius:8px}.x:hover{color:var(--bad)}
#msg{margin:8px 0 0;font-size:14px}#msg.bad{color:var(--bad)}#msg.ok{color:var(--ok)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}.chip2{padding:7px 13px;border:2px solid var(--line);border-radius:99px;background:var(--surface);color:var(--ink);font:inherit;font-size:14px;cursor:pointer}.chip2:hover{border-color:var(--brand);color:var(--brand)}
.sbox{display:flex;gap:8px;margin:2px 0 4px}
.sbox input[type=search],.sel{flex:1;min-width:0;padding:12px 14px;border:2px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);font-size:16px}
.sbox input:focus,.sel:focus{border-color:var(--brand);outline:none}
.btn{padding:12px 18px;border:0;border-radius:12px;background:var(--brand);color:#fff;font-weight:700;cursor:pointer;white-space:nowrap}
.btn{text-decoration:none;display:inline-flex;align-items:center;justify-content:center}
.btn.alt{background:var(--brand-soft);color:var(--brand)}.btn:disabled{opacity:.6;cursor:wait}
.hit{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:10px 14px;border:2px solid var(--line);border-radius:12px;margin-top:8px;background:var(--surface)}
.hit .n{min-width:0}.hit b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hit small{color:var(--mute)}
.note{color:var(--mute);font-size:14px;margin:8px 0 0}.note.bad{color:var(--bad)}
.tr{display:flex;gap:12px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}.tr:first-child{border-top:0}
.tr .rk{width:28px;font-weight:800;color:var(--mute);text-align:right;flex:none}.tr .n{flex:1;min-width:0}.tr .n b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tr small{color:var(--mute)}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}.filters .sel{flex:1;min-width:140px}
.pub{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.pub button,.pub a{font:inherit;font-size:13px;font-weight:600;padding:7px 11px;border-radius:10px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer;text-decoration:none}
.pub button:hover,.pub a:hover{border-color:var(--brand);color:var(--brand)}.pub .done{border-color:var(--ok);color:var(--ok)}
.pubnote{font-size:12.5px;color:var(--mute);margin:6px 0 0}
[hidden]{display:none!important}
</style></head><body><div class="wrap">

<header>
  <div class="logo"><svg viewBox="0 0 34 34" aria-hidden="true"><rect width="34" height="34" rx="9" fill="#5b5bf0"/><g fill="#fff"><rect x="6" y="7" width="4.4" height="20" rx="1"/><rect x="12" y="7" width="4.4" height="20" rx="1"/><rect x="18" y="7" width="4.4" height="20" rx="1"/><rect x="24" y="7" width="4.4" height="20" rx="1"/></g><g fill="#ffb703"><rect x="9" y="7" width="3.6" height="12" rx="1"/><rect x="21" y="7" width="3.6" height="12" rx="1"/></g></svg>Piano Studio AI</div>
  <span class="pill" title="Morceaux déjà téléchargés et vérifiés"><span class="dot" id="sdot"></span>Réserve : <b id="stock">…</b></span>
  <span class="pill" id="ver" title="Version du programme en cours d'exécution">v <b>…</b></span>
  <span class="pill" id="engine" title="Moteur utilisé pour fabriquer la vidéo">Moteur : <b>…</b></span>
</header>

<section class="card">
  <div class="step"><span class="num">1</span><div><h2>Niveau de difficulté</h2><p>Plus le tempo est rapide, plus c'est difficile à jouer.</p></div></div>
  <div class="grid g3" id="levels" role="radiogroup" aria-label="Niveau"></div>

  <div class="step" style="margin-top:26px"><span class="num">2</span><div><h2>Formats</h2><p>Un seul enregistrement de Synthesia donne les deux vidéos. Décochez-en une si besoin.</p></div></div>
  <div class="grid g2" id="formats" aria-label="Formats"></div>

  <div class="step" style="margin-top:26px"><span class="num">3</span><div><h2>Musique</h2><p>Laissez l'agent choisir, ou utilisez l'un de vos morceaux (fichiers MIDI).</p></div></div>
  <div class="sbox"><input type="search" id="q" placeholder="Rechercher un morceau (ex. Clair de Lune, Für Elise, Gymnopédie…)" aria-label="Rechercher un morceau"><button class="btn" id="qgo">Chercher</button><a class="btn alt" id="qweb" target="_blank" rel="noopener" title="Ouvre une recherche internet dans un nouvel onglet : vous téléchargez le fichier vous-même, puis vous le glissez ci-dessous">🔎 Sur le web</a></div>
  <div class="chips" id="pop" aria-label="Classiques populaires"></div>
  <div style="margin:8px 0 2px"><button class="btn alt" id="lat">✨ Voir les nouveautés (derniers morceaux libres de droits)</button></div>
  <div id="qres"></div>
  <div class="songs" id="songs" role="radiogroup" aria-label="Morceau" style="margin-top:12px"></div>
  <div class="drop" id="drop" tabindex="0"><b>＋ Ajouter mes morceaux</b>Glissez des fichiers .mid / .kar ici, ou cliquez pour les choisir</div>
  <input type="file" id="file" accept=".mid,.midi,.kar" multiple hidden>
  <p class="note" style="margin:6px 0 0">Les chansons récentes sont protégées : un fichier MIDI trouvé sur le web n'est pas forcément libre de droits. Sa publication peut entraîner une réclamation, la coupure du son ou la suppression de la vidéo.</p>
  <label class="rights"><input type="checkbox" id="rights"> Je confirme avoir les droits d'utiliser cette musique (composition à moi, domaine public ou licence qui l'autorise).</label>
  <p id="msg" hidden></p>

  <div class="row">
    <label class="sw">Langue des textes <select id="lang" class="sel" style="flex:none;padding:6px 10px"></select></label>
    <label class="sw" title="Durée maximale de l'enregistrement d'écran : il s'arrête là, même si le morceau n'est pas fini">Enregistrement max <input type="number" id="maxrec" min="30" max="300" step="10" class="sel" style="width:76px;flex:none"> secondes</label>
    <label class="sw"><input type="checkbox" id="synth" checked> Utiliser mon application Synthesia (sinon rendu intégré)</label>
    <label class="sw"><input type="checkbox" id="publish" checked> <span id="pubtxt">Publier automatiquement après le montage</span></label>
    <button class="btn alt" id="chk" style="padding:6px 12px;font-size:13px">Tester mes connexions</button>
    <span id="chkres" class="note" style="margin:0"></span>
    <span class="est" id="est"></span>
  </div>
</section>

<div class="cta"><button id="go">Créer</button></div>

<section class="card" id="job" hidden style="margin-top:18px">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><b>Création</b><span style="display:flex;gap:10px;align-items:center"><span class="chip" id="chip">En cours</span><button id="stoprec" class="stop">■ Arrêter l'enregistrement</button><button id="stop" class="stop ghost">Annuler</button></span></div>
  <ol class="stepper" id="stepper"></ol>
  <div class="now" id="now">…</div>
  <div class="bar" id="bar"><i></i></div>
  <p class="err" id="err" hidden></p>
  <details><summary>Détails techniques</summary><pre id="log"></pre></details>
  <div class="res" id="res"></div>
</section>

<section class="card">
  <div class="step"><div><h2>Tendances du moment</h2><p>Classements musicaux par pays. Ces titres sont en général protégés : l'agent cherche une version libre de droits (surtout en classique).</p></div></div>
  <div class="filters"><select id="tc" class="sel"></select><select id="tg" class="sel"><option value="all">Tous styles</option><option value="classical">Classique</option></select><button class="btn alt" id="tgo">Afficher</button></div>
  <div id="tres"><p class="empty">Cliquez sur « Afficher » pour consulter les tendances.</p></div>
</section>

<section class="card" id="inbox">
  <div class="step"><div><h2>Mon dossier MIDI</h2><p>L'agent lit les fichiers .mid / .midi / .kar de ce dossier de ton ordinateur et fabrique les vidéos avec. Tes fichiers ne sont ni déplacés ni modifiés.</p></div></div>
  <div class="sbox"><input type="text" id="fpath" placeholder="/Users/toi/Desktop/MIDI" aria-label="Dossier MIDI"><button class="btn alt" id="fsave">Utiliser ce dossier</button><button class="btn" id="fscan">📥 Importer maintenant</button></div>
  <p class="note" id="fstat" style="margin:8px 0 6px">…</p>
  <label class="rights"><input type="checkbox" id="ibrights"> Je confirme que les fichiers de ce dossier sont libres de droits, ou que j'ai le droit de les utiliser. Une chanson récente n'est pas libre : sa publication peut entraîner une réclamation, la coupure du son ou la suppression de la vidéo.</label>
  <details style="margin-top:8px"><summary>Réception automatique par un autre programme</summary>
    <p class="note">Dossier de réception : <code id="ibpath">…</code> · en attente : <b id="ibwait">0</b> · reçus : <b id="ibdone">0</b><br>Envoi direct : <code>curl -X POST --data-binary @fichier.mid -H "X-Filename: Artiste - Titre.mid" http://127.0.0.1:8765/api/inbox</code></p></details>
</section>

<section class="card" id="sched">
  <div class="step"><div><h2>Programmation</h2><p>L'agent fabrique les vidéos puis les publie tout seul à l'heure choisie. Laisse cette page ouverte et le Mac allumé (il ne se met pas en veille tant que la page tourne).</p></div></div>
  <div class="row">
    <label class="sw">Vidéos <input type="number" id="wcount" value="14" min="1" max="30" class="sel" style="width:76px;flex:none"></label>
    <label class="sw">Temps de fabrication (min) <input type="number" id="wmin" value="30" min="5" max="600" class="sel" style="width:84px;flex:none"></label>
    <label class="sw">Par jour <input type="number" id="wper" value="2" min="1" max="6" class="sel" style="width:64px;flex:none"></label>
    <label class="sw">Heures <input type="text" id="wtimes" value="12:30, 19:00" class="sel" style="width:130px;flex:none" aria-label="Heures de publication"></label>
    <label class="sw">Premier jour <input type="date" id="wday" class="sel" style="flex:none"></label>
  </div>
  <label class="sw" style="margin:6px 0"><input type="checkbox" id="wnow"> Publier dès que chaque vidéo est montée (sans attendre les heures)</label>
  <p class="note" id="west" style="margin:4px 0 8px"></p>
  <div class="row"><button class="btn" id="wgo">🗓 Fabriquer et programmer</button><button class="btn alt" id="wplan">Programmer les vidéos déjà prêtes</button><span id="wmsg" class="note" style="margin:0"></span></div>
  <div id="slist"></div>
</section>

<section class="card hist">
  <div class="step"><div><h2>Vidéos récentes</h2></div></div>
  <div id="vids"><p class="empty">Aucune vidéo pour l'instant.</p></div>
  <div id="player"></div>
</section>

<script>
const $=s=>document.querySelector(s);
let songId=null,level=null,formats=new Set(),since=0,timer=null,opts=null,cur=-1,fmtLabel='';
const api=(p,o)=>fetch(p,o).then(r=>r.json());
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const STEPS=['Morceau','Passage','Fabrication','Qualité','Publication'];
const dev=f=>f.width>f.height
  ?'<svg width="64" height="40" viewBox="0 0 64 40" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="3" width="58" height="34" rx="6"/><path d="M12 28h40" stroke-width="5" stroke-linecap="round" opacity=".35"/></svg>'
  :'<svg width="40" height="64" viewBox="0 0 40 64" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="3" width="34" height="58" rx="7"/><path d="M12 52h16" stroke-width="5" stroke-linecap="round" opacity=".35"/></svg>';
const estimate=()=>{const n=formats.size;$('#est').textContent=n?`Environ ${[...formats].some(k=>opts.formats.find(f=>f.key===k).long)?'4 à 5':'2 à 3'} minutes${n>1?' pour les deux vidéos (un seul enregistrement)':''}`:'Choisissez au moins un format';
  $('#go').disabled=!n||!level;$('#go').textContent=n>1?'Créer les 2 vidéos':n===1?'Créer la vidéo':'Choisissez un format'};
function render(){
  $('#levels').innerHTML=opts.levels.map((l,i)=>`<button class="opt" role="radio" aria-checked="${l.key===level}" data-k="${l.key}"><span class="tick">✓</span><span class="t">${esc(l.label)}</span><span class="bpm">${l.bpm}<small>BPM</small></span><span class="meter">${[0,1,2].map(j=>`<i class="${j<=i?'on':''}"></i>`).join('')}</span></button>`).join('');
  $('#formats').innerHTML=opts.formats.map(f=>`<button class="opt dev" role="checkbox" aria-checked="${formats.has(f.key)}" data-k="${f.key}"><span class="tick">✓</span>${dev(f)}<span><span class="t">${esc(f.label.split(' (')[0])}</span><span class="d">${esc((f.label.match(/\(([^)]+)\)/)||[,''])[1])}</span><span class="d">${f.width}×${f.height} · ${f.long?'morceau entier (1 à 2 min 30)':'environ 1 minute'}</span></span></button>`).join('');
  estimate()}
$('#levels').onclick=e=>{const b=e.target.closest('.opt');if(b){level=b.dataset.k;render()}};
$('#formats').onclick=e=>{const b=e.target.closest('.opt');if(!b)return;const k=b.dataset.k;formats.has(k)?formats.delete(k):formats.add(k);render()};
const webUrl=q=>'https://www.google.com/search?q='+encodeURIComponent((q||'').trim()+' midi');
function syncWeb(){$('#qweb').href=webUrl($('#q').value||'piano')}
$('#q').addEventListener('input',syncWeb);syncWeb();
const ORIGIN={mine:'Mon MIDI',reserve:'Réserve',auto:'Auto'};
function songs(){api('/api/songs').then(list=>{
  const row=(id,title,sub,tag,mine)=>`<div class="song" role="radio" tabindex="0" aria-checked="${songId===id}" data-id="${id??''}"><span class="n"><b>${esc(title)}</b><small>${esc(sub)}</small></span>${tag?`<span class="tag ${mine?'mine':''}">${tag}</span>`:''}${mine?`<button class="x" data-del="${id}" title="Retirer de ma bibliothèque" aria-label="Retirer">✕</button>`:''}</div>`;
  $('#songs').innerHTML=row(null,'Automatique','L\'agent choisit un morceau dans la réserve',null,false)+list.map(s=>row(s.id,s.title,s.artist||'',ORIGIN[s.origin]||'',s.origin==='mine')).join('')})}
$('#songs').onclick=e=>{const d=e.target.closest('[data-del]');if(d){e.stopPropagation();if(+d.dataset.del===songId)songId=null;api('/api/songs/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:+d.dataset.del})}).then(songs);return}
  const r=e.target.closest('.song');if(r){songId=r.dataset.id?+r.dataset.id:null;songs()}};
function say(m,ok){const e=$('#msg');e.hidden=false;e.textContent=m;e.className=ok?'ok':'bad'}
async function upload(files){
  if(!$('#rights').checked){say('Cochez d\'abord la case qui confirme que vous avez les droits sur cette musique.',false);return}
  for(const f of files){
    if(!/\.(midi?|kar)$/i.test(f.name)){say(`« ${f.name} » n'est pas un fichier MIDI (.mid, .kar). Un MP3 ne contient pas de notes.`,false);continue}
    const r=await fetch('/api/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(f.name),'X-Rights':'1'},body:f}).then(r=>r.json());
    say(`${f.name} : ${r.message||r.error}`,!r.error&&r.status!=='REJECTED');if(r.song_id&&!r.error)songId=r.song_id}
  songs()}
$('#drop').onclick=()=>$('#file').click();$('#drop').onkeydown=e=>{if(e.key==='Enter'||e.key===' ')$('#file').click()};
$('#file').onchange=e=>{upload([...e.target.files]);e.target.value=''};
['dragover','dragenter'].forEach(ev=>$('#drop').addEventListener(ev,e=>{e.preventDefault();$('#drop').classList.add('over')}));
['dragleave','drop'].forEach(ev=>$('#drop').addEventListener(ev,e=>{e.preventDefault();$('#drop').classList.remove('over')}));
$('#drop').addEventListener('drop',e=>upload([...e.dataTransfer.files]));
function hit(h){
  const lib=h.kind==='library';
  return `<div class="hit"><span class="n"><b>${esc(h.title)}</b><small>${esc(h.composer||'')} · ${lib?'Dans ma bibliothèque':'Libre de droits : '+esc(h.license)}</small></span>`+
    `<button class="btn ${lib?'alt':''}" ${lib?`data-use="${h.song_id}"`:`data-add="${esc(h.page)}"`}>${lib?'Utiliser':'Ajouter et utiliser'}</button></div>`}
function runSearch(q){
  q=(q||$('#q').value).trim();if(q.length<2){$('#qres').innerHTML='<p class="note">Tapez au moins 2 lettres.</p>';return}
  $('#q').value=q;$('#qgo').disabled=true;$('#qres').innerHTML='<p class="note">Recherche en cours…</p>';
  api('/api/search?q='+encodeURIComponent(q)).then(r=>{
    $('#qres').innerHTML=r.results.map(hit).join('')+(r.message?`<p class="note ${r.results.length?'':'bad'}">${esc(r.message)}</p>`:'');
    if(r.results.length)$('#qres').insertAdjacentHTML('afterbegin',`<p class="note" style="color:var(--ok);font-weight:700">✓ ${r.results.length} MIDI trouvé${r.results.length>1?'s':''} pour « ${esc(r.query)} »</p>`)
  }).catch(()=>{$('#qres').innerHTML='<p class="note bad">La recherche a échoué.</p>'}).finally(()=>{$('#qgo').disabled=false})}
api('/api/popular').then(l=>{$('#pop').innerHTML='<span class="note" style="margin:0 4px 0 0;align-self:center">Classiques :</span>'+l.map(x=>`<button class="chip2" data-pop="${esc(x.query)}" title="${esc(x.composer)}">${esc(x.title)}</button>`).join('')});
$('#pop').onclick=e=>{const b=e.target.closest('[data-pop]');if(b)runSearch(b.dataset.pop)};
$('#lat').onclick=()=>{$('#lat').disabled=true;$('#qres').innerHTML='<p class="note">Chargement des nouveautés…</p>';
  api('/api/latest').then(r=>{$('#qres').innerHTML=(r.results.length?`<p class="note" style="color:var(--ok);font-weight:700">✨ ${r.results.length} nouveautés libres de droits</p>`:'')+r.results.map(hit).join('')+(r.message?`<p class="note ${r.results.length?'':'bad'}">${esc(r.message)}</p>`:'')})
   .catch(()=>{$('#qres').innerHTML='<p class="note bad">Impossible de charger les nouveautés.</p>'}).finally(()=>{$('#lat').disabled=false})};
$('#qgo').onclick=()=>runSearch();$('#q').onkeydown=e=>{if(e.key==='Enter')runSearch()};
$('#qres').onclick=e=>{const u=e.target.closest('[data-use]'),a=e.target.closest('[data-add]');
  if(u){songId=+u.dataset.use;songs();$('#qres').innerHTML='<p class="note" style="color:var(--ok);font-weight:700">✓ Ce morceau sera utilisé.</p>'}
  if(a){a.disabled=true;a.textContent='Téléchargement…';api('/api/import-found',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({page:a.dataset.add})}).then(r=>{
    if(r.error){$('#qres').insertAdjacentHTML('beforeend',`<p class="note bad">${esc(r.error)}</p>`);a.disabled=false;a.textContent='Ajouter et utiliser';return}
    songId=r.song_id;songs();$('#qres').innerHTML=`<p class="note" style="color:var(--ok);font-weight:700">✓ ${esc(r.message)} Il sera utilisé pour la création.</p>`})}};
$('#tgo').onclick=()=>{$('#tgo').disabled=true;$('#tres').innerHTML='<p class="empty">Chargement…</p>';
  api(`/api/trends?country=${$('#tc').value}&genre=${$('#tg').value}`).then(r=>{
    $('#tres').innerHTML=r.items.length?r.items.map(i=>`<div class="tr"><span class="rk">${i.rank}</span><span class="n"><b>${esc(i.title)}</b><small>${esc(i.artist)}</small></span><button class="btn alt" data-q="${esc(i.title)}">MIDI libre</button><a class="btn alt" target="_blank" rel="noopener" href="${webUrl(i.title+' '+i.artist)}">🔎 Web</a></div>`).join(''):`<p class="note bad">${esc(r.message||'Aucune tendance disponible.')}</p>`
  }).catch(()=>{$('#tres').innerHTML='<p class="note bad">Impossible de charger les tendances.</p>'}).finally(()=>{$('#tgo').disabled=false})};
$('#tres').onclick=e=>{const b=e.target.closest('[data-q]');if(b){$('#q').scrollIntoView({behavior:'smooth',block:'center'});runSearch(b.dataset.q)}};
function info(){api('/api/info').then(i=>{$('#pubtxt').innerHTML='Publier automatiquement après le montage : '+[['YouTube',i.youtube],['TikTok',i.tiktok]].map(([n,ok])=>`${n} <b style="color:var(--${ok?'ok':'bad'})">${ok?'✓':'non connecté'}</b>`).join(' · ');$('#ver').innerHTML=`version <b>${esc(i.version||'?')}</b>`;$('#stock').textContent=`${i.stock} morceau${i.stock>1?'x':''} d'avance`;$('#sdot').className='dot'+(i.stock>0?' on':'');
  $('#engine').innerHTML=`Moteur : <b>${i.engine==='synthesia'?'Synthesia':i.engine?'rendu intégré':'vérification…'}</b>`;$('#engine').title=i.engine==='synthesia'?'Votre application Synthesia pilotée automatiquement':'Synthesia non prêt : rendu intégré utilisé'})}
function vids(){api('/api/videos').then(v=>{if(!v.length)return;$('#vids').innerHTML=v.map(x=>`<div class="v"><div><b>${esc(x.title)}</b><br><small>${esc(x.level)} · ${esc(x.format)} · ${x.duration}s · qualité ${x.quality??'-'}/100 · ${esc(x.status)} · ${esc(x.at)}</small></div>${x.file?`<button data-f="${esc(x.file)}">Voir</button>`:''}</div>${x.file&&x.status!=='FAILED'?`<div class="pub"><button data-now="${x.id}">🚀 Publier maintenant</button><input type="datetime-local" data-when="${x.id}" class="sel" style="flex:none;padding:6px 8px"><button data-at="${x.id}">🗓 Programmer</button></div>`:''}${x.post&&x.file?pubBox(x.post):''}`).join('')})}
$('#vids').onclick=e=>{const f=e.target.dataset.f;if(f){$('#player').innerHTML=`<video controls autoplay playsinline style="width:100%;max-height:70vh;border-radius:12px;background:#000;margin-top:12px" src="/files/${encodeURIComponent(f)}"></video>`;$('#player').scrollIntoView({behavior:'smooth',block:'center'})}};
const POSTS=[];
function pubBox(post,wide){
  if(!post)return '';const i=POSTS.push(post)-1;
  const b=(k,l)=>post[k]?`<button data-post="${i}" data-k="${k}">${l}</button>`:'';
  return `<div class="pub">${b('tiktok_caption','Copier le texte TikTok')}${b('instagram_caption','Copier le texte Instagram')}${b('youtube_title','Copier le titre YouTube')}${b('description','Copier la description YouTube')}${b('pinned_comment','Copier le commentaire épinglé')}</div>`+
   `<div class="pub"><a href="https://www.tiktok.com/upload" target="_blank" rel="noopener">Ouvrir TikTok</a><a href="https://studio.youtube.com" target="_blank" rel="noopener">Ouvrir YouTube Studio</a><a href="https://business.facebook.com/latest/reels_composer" target="_blank" rel="noopener">Ouvrir Facebook</a><a href="https://www.instagram.com/" target="_blank" rel="noopener">Ouvrir Instagram</a></div>`}
document.addEventListener('click',e=>{const b=e.target.closest('[data-post]');if(!b)return;
  const txt=(POSTS[+b.dataset.post]||{})[b.dataset.k];if(!txt)return;
  const ok=()=>{const o=b.textContent;b.textContent='Copié ✓';b.classList.add('done');setTimeout(()=>{b.textContent=o;b.classList.remove('done')},1600)};
  (navigator.clipboard?navigator.clipboard.writeText(txt):Promise.reject()).then(ok).catch(()=>{const a=document.createElement('textarea');a.value=txt;document.body.appendChild(a);a.select();try{document.execCommand('copy');ok()}catch(_){}a.remove()})});
$('#chk').onclick=()=>{$('#chk').disabled=true;$('#chkres').textContent='Vérification…';
  api('/api/check-platforms').then(r=>{$('#chkres').innerHTML=r.length?r.map(x=>`<b style="color:var(--${x.ok?'ok':'bad'})">${x.ok?'✓':'✗'} ${esc(x.platform)}</b> ${esc(x.message)}`).join(' · '):'Aucune plateforme à tester.'})
   .catch(()=>{$('#chkres').textContent='Test impossible.'}).finally(()=>{$('#chk').disabled=false})};

const dfmt=iso=>new Date(iso).toLocaleString('fr-FR',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
function sched(){api('/api/schedule').then(d=>{
  const nm={PENDING:'⏳ programmée',RUNNING:'⏫ envoi en cours',DONE:'✅ publiée',FAILED:'❌ échec',MISSED:'⚠ manquée'};
  const un=d.unscheduled.length?`<p class="note" style="margin:10px 0 4px"><b>${d.unscheduled.length}</b> vidéo(s) prête(s) pas encore programmée(s).</p>`:'';
  $('#slist').innerHTML=un+(d.items.length?d.items.map(x=>`<div class="v"><div><b>${esc(x.title)}</b><br><small>${x.format==='horizontal'?'YouTube long':'TikTok + YouTube Shorts'} · ${esc(dfmt(x.run_at))} · ${nm[x.status]||esc(x.status)}${x.detail?' · '+esc(x.detail):''}</small></div>${x.status==='PENDING'?`<button data-cancel="${x.id}">Annuler</button>`:''}</div>`).join(''):'<p class="empty">Rien de programmé.</p>')})}
function inb(){api('/api/inbox').then(d=>{$('#ibpath').textContent=d.path;$('#ibwait').textContent=d.waiting;$('#ibdone').textContent=d.done;$('#ibrights').checked=d.rights;
  const f=(d.folders||[])[0];if(f&&document.activeElement!==$('#fpath'))$('#fpath').value=f.path;
  $('#fstat').innerHTML=(f?(f.exists?`<b>${f.files}</b> fichier(s) MIDI dans ce dossier · `:`<b style="color:var(--bad)">dossier introuvable</b> · `):'Aucun dossier choisi · ')+`<b>${d.waiting}</b> en attente d'import · <b>${d.to_make}</b> morceau(x) à transformer en vidéo (l'agent prend les tiens en premier, dans l'ordre d'arrivée)`+(d.last_check?` · vérifié il y a ${Math.max(0,Math.round(Date.now()/1000-d.last_check))} s (automatique, toutes les 30 s)`:'')+(!d.rights?' · <b style="color:var(--bad)">coche la case ci-dessous pour autoriser l\'import</b>':'');
  if(d.done>inb.last)songs();inb.last=d.done})}
$('#fsave').onclick=()=>api('/api/folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:$('#fpath').value})}).then(r=>{if(r.error){$('#fstat').textContent=r.error;return}inb()});
$('#fscan').onclick=()=>{$('#fstat').textContent='Import en cours…';api('/api/inbox/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>{if(r.error){$('#fstat').textContent=r.error;return}songs();inb();
  setTimeout(()=>{$('#fstat').insertAdjacentHTML('afterbegin',`<b style="color:var(--ok)">${r.imported} importé(s)</b>${r.duplicates?`, ${r.duplicates} déjà présent(s)`:''}${r.errors.length?`, <span style="color:var(--bad)">${r.errors.length} refusé(s) : ${esc(r.errors.slice(0,3).join(' ; '))}</span>`:''} — `)},400)})};
inb.last=0;$('#ibrights').onchange=e=>api('/api/inbox/rights',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:e.target.checked})}).then(inb);
function west(){const n=+$('#wcount').value||1,m=+$('#wmin').value||30,per=+$('#wper').value||1;const fit=Math.max(1,Math.floor(m/3.5));
  $('#west').textContent=`Compte environ 3 à 4 minutes de fabrication par morceau (les deux formats) : ${m} min = environ ${fit} morceau(x). ${n} vidéos à ${per}/jour = ${Math.ceil(n/per)} jour(s).`+(n>fit?' Augmente le temps ou baisse le nombre, sinon l\'agent s\'arrêtera à '+fit+' et programmera ce qu\'il a fait.':'')}
['wcount','wmin','wper'].forEach(i=>$('#'+i).oninput=west);
{const d=new Date();d.setDate(d.getDate()+1);$('#wday').value=d.toISOString().slice(0,10)}west();
function watch(txt){$('#job').hidden=false;$('#log').textContent='';$('#res').innerHTML='';$('#err').hidden=true;since=0;cur=-1;fmtLabel='';stepper();$('#now').textContent=txt||'En cours…';
  $('#job').scrollIntoView({behavior:'smooth',block:'start'});if(!timer)timer=setInterval(poll,1500);poll()}
const wbody=()=>({count:+$('#wcount').value,minutes:+$('#wmin').value,per_day:+$('#wper').value,times:$('#wtimes').value,first_day:$('#wday').value,immediate:$('#wnow').checked});
$('#wgo').onclick=()=>{if(!confirm('Lancer la fabrication de '+$('#wcount').value+' morceaux, puis programmer leur publication ? Ne touche pas au Mac pendant la fabrication.'))return;
  api('/api/week',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...wbody(),formats:[...formats],synthesia:$('#synth').checked,lang:$('#lang').value})})
   .then(r=>{if(r.error){$('#wmsg').textContent=r.error;return}$('#wmsg').textContent='';watch('Démarrage de la production…')})};
$('#wplan').onclick=()=>api('/api/schedule/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(wbody())})
  .then(r=>{$('#wmsg').textContent=r.error||r.message;sched()});
document.addEventListener('click',e=>{
  const c=e.target.closest('[data-cancel]');if(c){api('/api/schedule/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:+c.dataset.cancel})}).then(sched);return}
  const n=e.target.closest('[data-now]');if(n){if(!confirm('Publier cette vidéo maintenant ? Ne touche ni à la souris ni au clavier pendant l\'envoi.'))return;
    api('/api/publish-now',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:+n.dataset.now})}).then(r=>{if(r.error){alert(r.error);return}watch('Publication en cours…')});return}
  const s=e.target.closest('[data-at]');if(s){const v=document.querySelector(`input[data-when="${s.dataset.at}"]`).value;if(!v){alert('Choisis d\'abord la date et l\'heure.');return}
    api('/api/schedule/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_ids:[+s.dataset.at],at:v})}).then(r=>{if(r.error){alert(r.error);return}sched();s.textContent='Programmée ✓'})}});
function pubResult(x){
  if(!x.publications||!x.publications.length)return '';
  const names={youtube:x.format==='horizontal'?'YouTube (vidéo longue)':'YouTube Shorts',tiktok:'TikTok',outbox:'Dossier prêt à poster'};
  return '<div class="pubnote" style="margin-top:8px">'+x.publications.filter(p=>p.platform!=='outbox'||x.publications.length===1).map(p=>{
    const ok=p.status==='PUBLISHED'||p.status==='DRAFT'||p.status==='EXPORTED';
    const label=p.status==='PUBLISHED'?'publié':p.status==='DRAFT'?'brouillon prêt dans TikTok':p.status==='NOT_CONFIGURED'?'non connecté':p.status==='EXPORTED'?'prêt':'échec';
    const link=/^https?:/.test(p.detail||'')?` · <a href="${esc(p.detail.split(' ')[0])}" target="_blank" rel="noopener">voir</a>`:'';
    return `<b style="color:var(--${ok?'ok':p.status==='NOT_CONFIGURED'?'mute':'bad'})">${esc(names[p.platform]||p.platform)} : ${label}</b>${link}${!ok&&p.detail?' — '+esc(p.detail):''}`}).join('<br>')+'</div>'}
function stepper(){$('#stepper').innerHTML=STEPS.map((s,i)=>`<li class="${i<cur?'done':i===cur?'cur':''}">${i<cur?'✓ ':''}${s}</li>`).join('')}
function track(line){const m=line.match(/\[(vertical|horizontal)\]/);if(m)fmtLabel=m[1]==='vertical'?'Vertical':'Horizontal';
  const k=line.startsWith('♪')?0:/^[🔎✂]/u.test(line)?1:line.startsWith('🎬')?2:line.startsWith('✔')?3:line.startsWith('📤')?4:null;
  if(line.startsWith('✂'))cur=1;else if(k!==null&&k>cur)cur=k}
function results(r){const list=r.videos||[r];$('#res').innerHTML=list.filter(x=>x&&x.video).map(x=>{const f=x.video.split('/').pop(),bad=x.status==='FAILED';
  return `<div class="vid"><div class="meta"><span>${x.format==='horizontal'?'Horizontal long':'Vertical court'} ${x.engine?`<span class="tag ${x.engine==='synthesia'?'mine':''}">${x.engine==='synthesia'?'Fait avec Synthesia':'Rendu intégré'}</span>`:''}</span><span class="chip ${bad?'bad':'ok'}">${bad?'Échec':'Qualité '+(x.qc?x.qc.score:'-')+'/100'}</span></div>${bad?`<p class="err">${esc(x.error||'La fabrication a échoué')}</p>`:`<video controls playsinline preload="metadata" src="/files/${encodeURIComponent(f)}"></video><a href="/files/${encodeURIComponent(f)}" download="${esc(f)}">⬇ Télécharger</a>${pubBox(x.post)}${pubResult(x)}${x.post&&x.post.thumbnail?`<a href="/files/${encodeURIComponent(x.post.thumbnail)}" download="${esc(x.post.thumbnail)}" style="margin-left:14px">🖼 Miniature</a>`:''}`}</div>`}).join('')}
function poll(){api('/api/status?since='+since).then(s=>{
  since=s.last;const L=$('#log');s.logs.forEach(l=>track(l));
  if(s.logs.length){L.textContent+=s.logs.join('\n')+'\n';L.scrollTop=L.scrollHeight;const last=s.logs[s.logs.length-1];$('#now').textContent=(fmtLabel&&s.status==='running'?fmtLabel+' · ':'')+last.replace(/\s*\[(vertical|horizontal)\]\s*/,' ').trim()}
  stepper();const run=s.status==='running';$('#bar').hidden=!run;$('#stop').hidden=!run;$('#stoprec').hidden=!run;if(run&&!$('#stoprec').dataset.busy){$('#stop').disabled=false;$('#stoprec').disabled=false};if(!run)delete $('#stoprec').dataset.busy;estimate();if(run){$('#go').disabled=true;$('#go').textContent='Création en cours…'}
  $('#chip').textContent=run?'En cours':s.status==='done'?'Terminé':s.status==='cancelled'?'Arrêté':'Échec';$('#chip').className='chip '+(s.status==='done'?'ok':s.status==='failed'||s.status==='cancelled'?'bad':'');
  if(!run){clearInterval(timer);timer=null;vids();info();sched();cur=s.status==='done'?5:cur;stepper();
    if(s.status==='cancelled'){$('#now').textContent='Création arrêtée'}
    if(s.status==='failed'){$('#err').hidden=false;$('#err').textContent=s.error}
    else if(s.result&&s.result.task){$('#now').textContent='Terminé : '+s.result.summary}
    else if(s.result){$('#now').textContent='Terminé';results(Array.isArray(s.result)?{videos:s.result.flatMap(r=>r.videos||[r])}:s.result)}}
})}
$('#maxrec').onchange=()=>api('/api/setting',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'max_record_seconds',value:+$('#maxrec').value})}).then(r=>{if(r.error){alert(r.error);api('/api/options').then(o=>$('#maxrec').value=o.max_record_seconds)}else{$('#maxrec').value=r.max_record_seconds;estimate()}});
$('#stoprec').onclick=()=>{$('#stoprec').disabled=true;$('#stoprec').dataset.busy=1;$('#now').textContent='Arrêt de l\'enregistrement… la vidéo sera montée avec ce qui est enregistré';api('/api/stop-recording',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(()=>setTimeout(()=>{delete $('#stoprec').dataset.busy},4000))};
$('#stop').onclick=()=>{if(!confirm('Annuler la création ? Rien ne sera gardé.'))return;$('#stop').disabled=true;$('#now').textContent='Annulation… (Synthesia va se fermer)';api('/api/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})};
$('#go').onclick=()=>{
  $('#job').hidden=false;$('#log').textContent='';$('#res').innerHTML='';$('#err').hidden=true;since=0;cur=-1;fmtLabel='';stepper();$('#now').textContent='Démarrage…';
  $('#job').scrollIntoView({behavior:'smooth',block:'start'});
  api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({level,formats:[...formats],publish:$('#publish').checked,synthesia:$('#synth').checked,song_id:songId,lang:$('#lang').value})})
   .then(r=>{if(r.error){$('#now').textContent=r.error;return}if(!timer)timer=setInterval(poll,1500);poll()})};
api('/api/options').then(o=>{opts=o;$('#maxrec').value=o.max_record_seconds;$('#lang').innerHTML=o.languages.map(l=>`<option value="${l.key}"${l.key===o.default_language?' selected':''}>${l.label}</option>`).join('');$('#tc').innerHTML=o.countries.map(c=>`<option value="${c.key}">${c.label}</option>`).join('');level=(o.levels[1]||o.levels[0]).key;formats=new Set(o.default_formats);render()});
info();vids();songs();sched();inb();setInterval(info,20000);setInterval(sched,30000);setInterval(inb,10000);
api('/api/status').then(s=>{if(s.status==='running'){$('#job').hidden=false;since=0;timer=setInterval(poll,1500);poll()}});
</script></div></body></html>
"""
