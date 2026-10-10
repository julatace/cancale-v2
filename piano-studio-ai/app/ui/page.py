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
.sw input[type=checkbox]{appearance:none;width:44px;height:26px;border-radius:99px;background:var(--line);position:relative;cursor:pointer;transition:.15s;flex:none}
.sw input[type=checkbox]::after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;transition:.15s;box-shadow:0 1px 3px rgba(0,0,0,.3)}
.sw input[type=checkbox]:checked{background:var(--brand)}.sw input[type=checkbox]:checked::after{left:21px}
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
.bar i.det{animation:none;margin-left:0;transition:width .6s}#pct{font-size:13px;color:var(--mute);margin-top:6px}
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
.sbox input[type=search],.sbox input[type=text],.sel{flex:1;min-width:0;padding:12px 14px;border:2px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);font-size:16px}
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

/* ===== refonte : navigation par onglets, hiérarchie plus claire ===== */
:root{--bg:#f4f5fb;--surface:#fff;--ink:#0f1226;--mute:#5d6384;--line:#e4e6f2;--brand:#5146f0;--brand-soft:#eceaff;--r:18px;
  --shadow:0 1px 2px rgba(15,18,38,.05),0 10px 30px rgba(15,18,38,.06)}
@media (prefers-color-scheme:dark){:root{--bg:#090b19;--surface:#131630;--ink:#eef0ff;--mute:#9aa1c8;--line:#252a4d;--brand:#9a94ff;--brand-soft:#232662}}
body{background:radial-gradient(1200px 500px at 10% -10%,color-mix(in srgb,var(--brand) 14%,transparent),transparent),var(--bg)}
.wrap{max-width:1040px}
.topbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:4px 0 14px}
.topbar .logo{margin-right:auto}
.sub{font-size:13px;color:var(--mute);font-weight:500;display:block;margin-top:-2px}
.nav{position:sticky;top:0;z-index:20;display:flex;gap:4px;padding:6px;margin:0 0 20px;background:color-mix(in srgb,var(--surface) 88%,transparent);backdrop-filter:blur(14px);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);overflow-x:auto}
.nav button{flex:1;min-width:max-content;display:flex;align-items:center;justify-content:center;gap:8px;border:0;background:none;padding:11px 16px;border-radius:12px;font-weight:700;font-size:15px;color:var(--mute);cursor:pointer;transition:background .12s,color .12s}
.nav button:hover{color:var(--ink);background:var(--brand-soft)}
.nav button[aria-selected=true]{background:var(--brand);color:#fff}
.nav .b{font-size:12px;font-weight:800;min-width:20px;padding:1px 7px;border-radius:99px;background:color-mix(in srgb,currentColor 18%,transparent)}
.nav .b:empty,.nav .b[data-n="0"]{display:none}
.panel{animation:fade .18s ease}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.card{border-radius:var(--r);padding:24px}
.card h3{margin:0 0 4px;font-size:17px}
.lead{margin:0 0 16px;color:var(--mute);font-size:15px}
.hero{background:linear-gradient(135deg,var(--brand),color-mix(in srgb,var(--brand) 55%,#ff7ad9));color:#fff;border:0}
.hero h2{margin:0 0 4px;font-size:24px;letter-spacing:-.01em}.hero p{margin:0;opacity:.9}
.hero .btn{background:#fff;color:var(--brand)}
.two{display:grid;grid-template-columns:1.15fr 1fr;gap:18px;align-items:start}
@media(max-width:860px){.two{grid-template-columns:1fr}}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0 0}
.kv div{background:var(--bg);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.kv small{display:block;color:var(--mute);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.kv b{font-size:20px}
.statusline{display:flex;gap:8px;flex-wrap:wrap}
.pill.ok{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 35%,var(--line))}.pill.bad{color:var(--bad)}
.next{display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--surface);border:1px solid var(--line);border-radius:14px;font-size:14px;color:var(--mute)}
.next b{color:var(--ink)}
.help{font-size:14px;color:var(--mute);background:var(--bg);border:1px dashed var(--line);border-radius:14px;padding:12px 14px;margin-top:12px}
.help ol{margin:6px 0 0 18px;padding:0}
.fieldrow{display:grid;grid-template-columns:200px 1fr;gap:10px 18px;align-items:center;padding:14px 0;border-top:1px solid var(--line)}
.fieldrow:first-of-type{border-top:0}
.fieldrow label.k{font-weight:700}.fieldrow small{display:block;color:var(--mute);font-weight:400}
@media(max-width:640px){.fieldrow{grid-template-columns:1fr}}
.cta{padding:18px 0 10px;position:static!important;background:none!important}
.agenda-head{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center;margin:2px 0 12px}
.quick{display:flex;gap:6px;flex-wrap:wrap}.quick .btn{padding:7px 12px;font-size:13px}
.agenda{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:8px}
@media(max-width:760px){.agenda{grid-template-columns:repeat(2,1fr)}}
.day{background:var(--bg);border:2px solid var(--line);border-radius:14px;padding:10px;text-align:center;transition:.12s}
.day.on{border-color:var(--brand);background:var(--brand-soft)}
.day small{display:block;color:var(--mute);font-weight:700;text-transform:uppercase;font-size:11px;letter-spacing:.05em}
.day .d{font-size:20px;font-weight:800;line-height:1.2}
.day .c{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:6px}
.day .c b{font-size:22px;min-width:22px}
.day .c button{width:28px;height:28px;border-radius:50%;border:0;background:var(--surface);color:var(--ink);font-weight:800;font-size:16px;cursor:pointer;box-shadow:0 1px 2px rgba(0,0,0,.15)}
.day .c button:hover{background:var(--brand);color:#fff}
.row{justify-content:flex-start;gap:12px 20px}
.songs{overflow-x:hidden}.song{min-width:0}
@media(max-width:640px){.card{padding:16px;border-radius:16px}.wrap{padding-left:12px;padding-right:12px}.nav button{padding:10px 12px;font-size:14px}.sbox{flex-wrap:wrap}.sbox input{flex-basis:100%}}
#go{border-radius:16px;font-size:19px}
.how{margin:12px 0 0;padding:0;list-style:none;display:grid;gap:6px;font-size:15px}.how b{opacity:.95}
.fold{margin:0 0 14px;color:var(--ink)}.fold>summary{font-weight:700;font-size:16px;padding:12px 4px;color:var(--ink)}
.fold>summary:hover{color:var(--brand)}
#wgo{font-size:17px;padding:16px 26px}

/* ===== habillage v2 : accueil épuré ===== */
:root{--grad:linear-gradient(135deg,#5b4df5,#9a5cf0 60%,#ff7ab8)}
body{font-feature-settings:"ss01","cv11";letter-spacing:-.005em}
.topbar .logo>span{font-size:19px;font-weight:800}.topbar .logo .sub{font-size:13px;font-weight:500;color:var(--mute)}
.card{border-radius:22px;border:1px solid color-mix(in srgb,var(--line) 70%,transparent);box-shadow:0 1px 1px rgba(15,18,38,.04),0 14px 40px -12px rgba(40,30,120,.14)}
.pilot{padding:22px 24px;border:2px solid transparent;transition:border-color .2s,background .2s}
.pilot.on{border-color:color-mix(in srgb,var(--ok) 55%,transparent);background:linear-gradient(180deg,color-mix(in srgb,var(--ok) 7%,var(--surface)),var(--surface))}
.pilot-row{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap}
.sw.big{gap:14px;align-items:center;color:var(--ink)}
.sw.big input[type=checkbox]{width:58px;height:34px}
.sw.big input[type=checkbox]::after{width:28px;height:28px;top:3px;left:3px}
.sw.big input[type=checkbox]:checked{background:var(--ok)}.sw.big input[type=checkbox]:checked::after{left:27px}
.sw.big span{display:flex;flex-direction:column;gap:2px}.sw.big b{font-size:19px}.sw.big small{color:var(--mute);font-size:14px;font-weight:500;max-width:46ch}
.pilot-set{display:flex;gap:14px;flex-wrap:wrap}.pilot-set label{display:flex;flex-direction:column;gap:4px;font-size:12px;font-weight:700;color:var(--mute);text-transform:uppercase;letter-spacing:.05em}
.pilot-set .sel{width:92px;padding:9px 12px;font-size:16px;font-weight:700;text-transform:none;letter-spacing:0;color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px}
@media(max-width:700px){.tiles{grid-template-columns:1fr}}
.tile{background:var(--bg);border:1px solid var(--line);border-radius:16px;padding:14px 16px;min-height:78px}
.tile>small{display:block;color:var(--mute);font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
.tile>div{font-size:17px;line-height:1.35}.tile small{font-size:13px;color:var(--mute);font-weight:500}
.tile #tomake{font-size:28px;font-weight:800;letter-spacing:-.02em}
.how2{margin-top:14px}.how2 summary{font-weight:600}.how2 ol{margin:8px 0 4px 20px;padding:0;color:var(--ink);line-height:1.7}.how2 p{margin:6px 0 0}
#sched{padding:24px}#slist{margin-top:18px;padding-top:14px;border-top:1px solid var(--line);font-size:15px;line-height:1.6}
.agenda-head b{font-size:19px;letter-spacing:-.01em}
.day{background:var(--surface);border:1.5px solid var(--line);border-radius:16px;padding:12px 8px 10px;cursor:default}
.day:hover{border-color:color-mix(in srgb,var(--brand) 45%,var(--line))}
.day.on{background:var(--grad);border-color:transparent;color:#fff;box-shadow:0 10px 24px -10px rgba(110,80,240,.6)}
.day.on small{color:rgba(255,255,255,.8)}.day.on .c button{background:rgba(255,255,255,.95);color:var(--brand)}
.day .c button{width:32px;height:32px;background:var(--bg);transition:transform .08s,background .12s}.day .c button:active{transform:scale(.9)}
.day .c b{font-size:24px}
#wgo{width:100%;margin-top:6px;border-radius:16px;padding:18px;font-size:18px;font-weight:800;background:var(--grad);color:#fff;box-shadow:0 14px 30px -12px rgba(110,80,240,.7);transition:filter .12s,transform .08s}
#wgo:hover:not(:disabled){filter:brightness(1.07)}#wgo:active:not(:disabled){transform:scale(.995)}#wgo:disabled{background:var(--line);color:var(--mute);box-shadow:none}
#job{border:2px solid color-mix(in srgb,var(--brand) 50%,transparent);background:linear-gradient(180deg,color-mix(in srgb,var(--brand) 6%,var(--surface)),var(--surface))}
#job .stepper{display:none}
#job .now{font-size:20px;margin:10px 0 12px}
#job .bar{height:12px;border-radius:99px}#job .bar i{background:var(--grad);border-radius:99px}
#pct{font-size:14px;font-weight:600;margin-top:10px}
.hist .v{padding:14px 0}
.nav{border-radius:18px;padding:5px}.nav button{padding:12px 14px}
.nav button[aria-selected=true]{background:var(--grad);box-shadow:0 8px 18px -8px rgba(110,80,240,.7)}
.pill{box-shadow:0 1px 2px rgba(15,18,38,.05)}
@media(max-width:560px){.agenda{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:6px}.day{padding:10px 4px 8px}.day .d{font-size:16px}.day .c{gap:4px}.day .c button{width:26px;height:26px}.day .c b{font-size:20px;min-width:16px}.nav button{min-width:0;padding:11px 6px;font-size:13px;gap:4px}.nav{overflow:visible}.wrap{padding:14px 12px 90px}.card,#sched,.pilot{padding:18px 16px;border-radius:18px}.agenda{grid-template-columns:repeat(3,1fr)}.sw.big b{font-size:17px}}

details.fold{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:2px 18px;margin:0 0 14px;box-shadow:0 1px 1px rgba(15,18,38,.03),0 10px 28px -14px rgba(40,30,120,.12)}
details.fold>summary{padding:15px 0;list-style:none;display:flex;align-items:center;justify-content:space-between}
details.fold>summary::after{content:"＋";font-size:20px;color:var(--brand);font-weight:800}
details.fold[open]>summary::after{content:"－"}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>.card{box-shadow:none;border:0;padding:6px 0 16px;margin:0;background:none}
.btn{background:var(--grad);box-shadow:0 8px 18px -10px rgba(110,80,240,.8)}.btn.alt{background:var(--brand-soft);box-shadow:none}
.btn:hover:not(:disabled){filter:brightness(1.06)}
</style></head><body><div class="wrap">

<div class="topbar">
  <div class="logo"><svg viewBox="0 0 34 34" aria-hidden="true"><rect width="34" height="34" rx="9" fill="#5146f0"/><g fill="#fff"><rect x="6" y="7" width="4.4" height="20" rx="1"/><rect x="12" y="7" width="4.4" height="20" rx="1"/><rect x="18" y="7" width="4.4" height="20" rx="1"/><rect x="24" y="7" width="4.4" height="20" rx="1"/></g><g fill="#ffb703"><rect x="9" y="7" width="3.6" height="12" rx="1"/><rect x="21" y="7" width="3.6" height="12" rx="1"/></g></svg><span>Piano Studio<span class="sub">Tutoriels piano : fabriqués et publiés automatiquement</span></span></div>
  <div class="statusline">
    <span class="pill" id="engine" hidden></span>
    <span class="pill" id="pill-tt">TikTok …</span>
    <span class="pill" id="pill-yt">YouTube …</span>
    <span class="pill" id="ver" title="Version du programme en cours d'exécution">v <b>…</b></span>
    <span class="pill" hidden><span class="dot" id="sdot"></span><b id="stock">…</b></span>
  </div>
</div>

<nav class="nav" role="tablist" aria-label="Sections">
  <button role="tab" data-tab="home" aria-selected="true">🏠 Accueil <span class="b" id="b-sch"></span></button>
  <button role="tab" data-tab="library" aria-selected="false">🎵 Mes morceaux <span class="b" id="b-lib"></span></button>
  <button role="tab" data-tab="settings" aria-selected="false">⚙ Réglages</button>
</nav>

<section class="card" id="job" hidden style="margin-top:18px">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><b>Création</b><span style="display:flex;gap:10px;align-items:center"><span class="chip" id="chip">En cours</span><button id="stoprec" class="stop">■ Arrêter l'enregistrement</button><button id="stop" class="stop ghost">Arrêter</button></span></div>
  <ol class="stepper" id="stepper"></ol>
  <div class="now" id="now">…</div>
  <div class="bar" id="bar"><i></i></div><div id="pct"></div>
  <p class="err" id="err" hidden></p>
  <details><summary>Détails techniques</summary><pre id="log"></pre></details>
  <div class="res" id="res"></div>
</section>

<main class="panel" id="tab-library" role="tabpanel" hidden>
<section class="card" id="inbox">
  <div class="step"><div><h2>Mon dossier MIDI</h2><p>L'agent lit les fichiers .mid / .midi / .kar de ce dossier de ton ordinateur et fabrique les vidéos avec. Tes fichiers ne sont ni déplacés ni modifiés.</p></div></div>
  <div class="sbox"><input type="text" id="fpath" placeholder="/Users/toi/Desktop/MIDI" aria-label="Dossier MIDI"><button class="btn alt" id="fsave">Utiliser ce dossier</button><button class="btn" id="fscan">📥 Importer maintenant</button></div>
  <p class="note" id="fstat" style="margin:8px 0 6px">…</p>
  <label class="rights"><input type="checkbox" id="ibrights"> Je confirme que les fichiers de ce dossier sont libres de droits, ou que j'ai le droit de les utiliser. Une chanson récente n'est pas libre : sa publication peut entraîner une réclamation, la coupure du son ou la suppression de la vidéo.</label>
  <details style="margin-top:8px"><summary>Réception automatique par un autre programme</summary>
    <p class="note">Dossier de réception : <code id="ibpath">…</code> · en attente : <b id="ibwait">0</b> · reçus : <b id="ibdone">0</b><br>Envoi direct : <code>curl -X POST --data-binary @fichier.mid -H "X-Filename: Artiste - Titre.mid" http://127.0.0.1:8765/api/inbox</code></p></details>
</section>


<details class="fold"><summary>➕ Ajouter ou chercher des morceaux</summary>
<section class="card">
  <div class="step"><div><h2>Ajouter, chercher</h2><p>Un fichier MIDI à toi, une recherche sur Mutopia (libre de droits), ou une recherche sur internet.</p></div></div>
  <div class="sbox"><input type="search" id="q" placeholder="Rechercher un morceau (ex. Clair de Lune, Für Elise, Gymnopédie…)" aria-label="Rechercher un morceau"><button class="btn" id="qgo">Chercher</button><a class="btn alt" id="qweb" target="_blank" rel="noopener" title="Ouvre une recherche internet dans un nouvel onglet : vous téléchargez le fichier vous-même, puis vous le glissez ci-dessous">🔎 Sur le web</a></div>
  <div class="chips" id="pop" aria-label="Classiques populaires"></div>
  <div style="margin:8px 0 2px"><button class="btn alt" id="lat">✨ Voir les nouveautés (derniers morceaux libres de droits)</button></div>
  <div id="qres"></div>
  <div class="drop" id="drop" tabindex="0"><b>＋ Ajouter mes morceaux</b>Glissez des fichiers .mid / .kar ici, ou cliquez pour les choisir</div>
  <input type="file" id="file" accept=".mid,.midi,.kar" multiple hidden>
  <p class="note" style="margin:6px 0 0">Les chansons récentes sont protégées : un fichier MIDI trouvé sur le web n'est pas forcément libre de droits. Sa publication peut entraîner une réclamation, la coupure du son ou la suppression de la vidéo.</p>
  <label class="rights"><input type="checkbox" id="rights"> Je confirme avoir les droits d'utiliser cette musique (composition à moi, domaine public ou licence qui l'autorise).</label>
  <p id="msg" hidden></p>

</section>
</details>
<details class="fold"><summary>📈 Tendances du moment</summary>
<section class="card">
  <div class="step"><div><h2>Tendances du moment</h2><p>Classements musicaux par pays. Ces titres sont en général protégés : l'agent cherche une version libre de droits (surtout en classique).</p></div></div>
  <div class="filters"><select id="tc" class="sel"></select><select id="tg" class="sel"><option value="all">Tous styles</option><option value="classical">Classique</option></select><button class="btn alt" id="tgo">Afficher</button></div>
  <div id="tres"><p class="empty">Cliquez sur « Afficher » pour consulter les tendances.</p></div>
</section>
</details>

</main>
<main class="panel" id="tab-schedule" role="tabpanel" hidden>
<section class="card pilot" id="auto">
  <div class="pilot-row">
    <label class="sw big"><input type="checkbox" id="apon"><span><b id="aplabel">Pilote automatique</b><small id="apmsg">…</small></span></label>
    <div class="pilot-set">
      <label>Par jour <select id="apday" class="sel"><option>1</option><option>2</option><option>3</option><option>4</option></select></label>
      <label>Avance <select id="apdays" class="sel"><option value="3">3 j</option><option value="5">5 j</option><option value="7">7 j</option><option value="9">9 j</option></select></label>
    </div>
  </div>
  <div class="tiles">
    <div class="tile"><small>Dernières 24 h</small><div id="health">…</div></div>
    <div class="tile"><small>Prochaine mise en ligne</small><div id="nextpub">Aucune publication programmée.</div></div>
    <div class="tile"><small>Morceaux prêts</small><div><b id="tomake">–</b></div></div>
  </div>
  <details class="how2"><summary>Comment ça marche ?</summary>
    <ol><li>Mets tes morceaux <b>.mid</b> dans le dossier <b>Bureau/MIDI</b>.</li><li>Active le <b>pilote automatique</b> : il garde l'agenda plein tout seul.</li><li>Ou choisis toi-même le nombre de vidéos par jour ci-dessous et clique sur <b>Fabriquer et programmer</b>.</li></ol>
    <p>Chaque vidéo est envoyée à TikTok et YouTube puis programmée dans leurs plannings : tu peux éteindre le Mac.</p>
  </details>
</section>
<section class="card" id="sched">
  <div class="agenda-head"><b>Combien de vidéos veux-tu publier chaque jour ?</b>
    <span class="quick"><button class="btn alt" data-quick="2">2 par jour (7 jours)</button><button class="btn alt" data-quick="1">1 par jour (7 jours)</button><button class="btn alt" data-quick="0">Tout effacer</button></span></div>
  <div class="agenda" id="agenda" role="group" aria-label="Agenda des prochains jours"></div>
  <details><summary>Options (heures de publication…)</summary>
  <div class="row" style="margin-top:14px;border:0;padding:0">
    <label class="sw">Heures de publication <input type="text" id="wtimes" value="12:30, 19:00" class="sel" style="width:150px;flex:none" aria-label="Heures de publication"></label>
    <label class="sw"><input type="checkbox" id="wnow"> Publier tout de suite, sans programmer <small style="color:var(--mute)">(sinon chaque vidéo est <b>programmée dans TikTok et YouTube</b> à la date de l'agenda)</small></label>
  </div>
  </details>
  <p class="note" id="west" style="margin:8px 0"></p>
  <div class="row" style="border:0;padding:0;margin-top:6px"><button class="btn" id="wgo">🚀 Fabriquer et programmer</button><button class="btn alt" id="wplan" title="Utilise les vidéos déjà prêtes au lieu d'en fabriquer" hidden>Envoyer et programmer les vidéos déjà prêtes</button><span id="wmsg" class="note" style="margin:0"></span></div>
  <div id="slist"></div>
</section>

</main>
<main class="panel" id="tab-videos" role="tabpanel" hidden>
<section class="card hist">
  <div class="step"><div><h2>Vidéos récentes</h2></div></div>
  <div id="vids"><p class="empty">Aucune vidéo pour l'instant.</p></div>
  <div id="player"></div>
</section>

</main>
<main class="panel" id="tab-settings" role="tabpanel" hidden>
<section class="card">
  <div class="step"><div><h2>Connexions</h2><p>Vérifie que l'agent peut publier sur tes comptes.</p></div></div>
  <div class="row" style="margin-top:0;border:0;padding-top:0"><button class="btn" id="chk">Tester mes connexions</button><span id="chkres" class="note" style="margin:0"></span></div>
  <div class="help"><b>Si une publication ne part pas :</b>
    <ol><li>Dans Chrome, ouvre le profil du compte (angeled92) et connecte-toi à TikTok et YouTube.</li>
    <li>Dans ce profil : menu <b>Présentation → Développeur → « Autoriser JavaScript dans Apple Events »</b>.</li>
    <li>Ne touche pas à la souris ni au clavier pendant un envoi.</li></ol></div>
</section>
<section class="card">
  <div class="step"><div><h2>Textes des vidéos</h2></div></div>
  <div class="fieldrow"><label class="k" for="lang">Langue des textes<small>Titres, descriptions, hashtags</small></label><select id="lang" class="sel" style="max-width:220px"></select></div>
  <details><summary>Avancé</summary>
  <div class="fieldrow"><label class="k" for="maxrec">Enregistrement maximum<small>L'enregistrement d'écran s'arrête là, même si le morceau n'est pas fini</small></label><span><input type="number" id="maxrec" min="30" max="300" step="10" class="sel" style="width:100px;flex:none"> secondes</span></div>
  <div class="fieldrow"><label class="k" for="synth">Application Synthesia<small>Décoché : style dessiné, sans aucune application</small></label><label class="sw"><input type="checkbox" id="synth"> Utiliser Synthesia à la place</label></div>
  </details>
</section>
</main>
<main class="panel" id="tab-create" role="tabpanel">
<details class="fold"><summary>🎬 Créer une seule vidéo à la main (facultatif)</summary>
<section class="card">
  <div class="step"><span class="num">1</span><div><h2>Morceau</h2><p>Par défaut, l'agent prend le prochain morceau de ton dossier MIDI (Bureau). Tu peux aussi en choisir un précis.</p></div></div>
  <div class="songs" id="songs" role="radiogroup" aria-label="Morceau"></div>
  <p class="note">Pour ajouter, chercher ou importer des morceaux : onglet <b>🎵 Bibliothèque</b>.</p>

  <div class="step" style="margin-top:28px"><span class="num">2</span><div><h2>Niveau</h2><p>Plus le tempo est rapide, plus c'est difficile. L'agent ralentit tout seul les passages trop rapides à lire.</p></div></div>
  <div class="grid g3" id="levels" role="radiogroup" aria-label="Niveau"></div>

  <div class="step" style="margin-top:28px"><span class="num">3</span><div><h2>Formats</h2><p>Un seul enregistrement donne les deux vidéos : le vertical (TikTok + YouTube Short) et l'horizontal (YouTube).</p></div></div>
  <div class="grid g2" id="formats" aria-label="Formats"></div>

  <div class="step" style="margin-top:28px"><span class="num">4</span><div><h2>Après le montage</h2><p>Pour mettre en ligne à une date précise, utilise l'onglet <b>Programmation</b> : la date est réglée dans TikTok et YouTube eux-mêmes.</p></div></div>
  <label class="sw"><input type="checkbox" id="publish"> <span id="pubtxt">Publier tout de suite après le montage</span></label>
  <p class="est" id="est" style="margin:10px 0 0"></p>
</section>
<div class="cta"><button id="go">Créer</button></div>
</details>
</main>

<script>
const $=s=>document.querySelector(s);
const TABS=['create','library','schedule','videos','settings'],GROUPS={home:['schedule','videos'],library:['library'],settings:['settings','create']};
function tab(n,noScroll){if(!GROUPS[n])n='home';TABS.forEach(t=>{$('#tab-'+t).hidden=!GROUPS[n].includes(t)});document.querySelectorAll('.nav [data-tab]').forEach(b=>b.setAttribute('aria-selected',b.dataset.tab===n));
  try{history.replaceState(null,'','#'+n);localStorage.setItem('tab',n)}catch(e){}if(!noScroll)window.scrollTo({top:0,behavior:'smooth'})}
document.querySelector('.nav').onclick=e=>{const b=e.target.closest('[data-tab]');if(b)tab(b.dataset.tab)};
tab((location.hash||'').slice(1)||(()=>{try{return localStorage.getItem('tab')}catch(e){return ''}})()||'home',true);

let songId=null,level=null,formats=new Set(),since=0,timer=null,opts=null,cur=-1,fmtLabel='';
const api=(p,o)=>fetch(p,o).then(r=>r.json());
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let ENGINE='',ONLY_MINE=false,PENDING_N=0,READY_N=0,READY_T=[],YT_DAILY=4;
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
  $('#songs').innerHTML=row(null,ONLY_MINE?'Le prochain de mon dossier MIDI':'Automatique',ONLY_MINE?'L\'agent prend le morceau suivant dans ton dossier (les nouveaux sons sont détectés tout seuls)':'L\'agent choisit un morceau',null,false)+(ONLY_MINE?list.filter(s=>s.origin==='mine'):list).map(s=>row(s.id,s.title,s.artist||'',ORIGIN[s.origin]||'',s.origin==='mine')).join('')})}
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
function info(){api('/api/info').then(i=>{if(ONLY_MINE!==!!i.only_mine){ONLY_MINE=!!i.only_mine;songs()}$('#pubtxt').innerHTML='Publier tout de suite après le montage (sinon : onglet Programmation) : '+[['YouTube',i.youtube],['TikTok',i.tiktok]].map(([n,ok])=>`${n} <b style="color:var(--${ok?'ok':'bad'})">${ok?'✓':'non connecté'}</b>`).join(' · ');ENGINE=i.engine||'';$('#ver').innerHTML=`v <b>${esc(i.version||'?')}</b>`;if($('#tomake'))$('#tomake').textContent=i.to_make!=null?String(i.to_make):'–';[['#pill-tt','TikTok',i.tiktok],['#pill-yt','YouTube',i.youtube]].forEach(([s,n,ok])=>{$(s).textContent=(ok?'✓ ':'✗ ')+n;$(s).className='pill '+(ok?'ok':'bad')});if(i.only_mine){$('#stock').textContent=`${i.to_make} à faire`;$('#sdot').className='dot'+(i.to_make>0?' on':'');$('#stock').parentElement.childNodes[1].textContent='Dossier MIDI : '}else{$('#stock').textContent=`${i.stock} morceau${i.stock>1?'x':''} d'avance`;$('#sdot').className='dot'+(i.stock>0?' on':'')}
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
  const pend=d.items.filter(x=>x.status==='PENDING');PENDING_N=pend.length;$('#b-sch').textContent=pend.length||'';
  const up=d.items.filter(x=>x.status==='DONE'&&new Date(x.run_at)>new Date()).sort((a,b)=>a.run_at<b.run_at?-1:1);
  $('#nextpub').innerHTML=up.length?`<b>${esc(dfmt(up[0].run_at))}</b><br><small>${esc(up[0].title)} · ${up.length} programmée${up.length>1?'s':''}</small>`:'<small>Rien de programmé pour l\'instant</small>';
  const un=d.unscheduled.length?`<p class="note" style="margin:10px 0 4px"><b>${d.unscheduled.length}</b> vidéo(s) prête(s) pas encore programmée(s).</p>`:'';
  $('#slist').innerHTML=un+(pend.length?`<p style="margin:8px 0"><button class="btn alt" data-cancelall="1">Tout annuler (${pend.length} publications programmées dans l\'app)</button></p>`:'')+(d.items.length?d.items.map(x=>`<div class="v"><div><b>${esc(x.title)}</b><br><small>${x.format==='horizontal'?'YouTube long':'TikTok + YouTube Shorts'} · ${esc(dfmt(x.run_at))} · ${nm[x.status]||esc(x.status)}${x.detail?' · '+esc(x.detail):''}</small></div>${x.status==='PENDING'?`<button data-cancel="${x.id}">Annuler</button>`:''}</div>`).join(''):'<p class="empty">Rien de programmé.</p>')})}
function inb(){api('/api/inbox').then(d=>{$('#ibpath').textContent=d.path;$('#ibwait').textContent=d.waiting;$('#ibdone').textContent=d.done;$('#b-lib').textContent=d.to_make||'';$('#b-lib').dataset.n=d.to_make||0;$('#ibrights').checked=d.rights;
  const f=(d.folders||[])[0];if(f&&document.activeElement!==$('#fpath'))$('#fpath').value=f.path;
  $('#fstat').innerHTML=(f?(f.exists?`<b>${f.files}</b> fichier(s) MIDI dans ce dossier · `:`<b style="color:var(--bad)">dossier introuvable</b> · `):'Aucun dossier choisi · ')+`<b>${d.waiting}</b> fichier(s) MIDI à importer · <b>${d.to_make}</b> morceau(x) à transformer en vidéo (l'agent prend les tiens en premier, dans l'ordre d'arrivée)`+(d.last_check?` · vérifié il y a ${Math.max(0,Math.round(Date.now()/1000-d.last_check))} s (automatique, toutes les 30 s)`:'')+(!d.rights?' · <b style="color:var(--bad)">coche la case ci-dessous pour autoriser l\'import</b>':'');
  if(d.done>inb.last)songs();inb.last=d.done})}
$('#fsave').onclick=()=>api('/api/folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:$('#fpath').value})}).then(r=>{if(r.error){$('#fstat').textContent=r.error;return}inb()});
$('#fscan').onclick=()=>{$('#fstat').textContent='Import en cours…';api('/api/inbox/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>{if(r.error){$('#fstat').textContent=r.error;return}songs();inb();
  setTimeout(()=>{$('#fstat').insertAdjacentHTML('afterbegin',`<b style="color:var(--ok)">${r.imported} importé(s)</b>${r.duplicates?`, ${r.duplicates} déjà présent(s)`:''}${r.errors.length?`, <span style="color:var(--bad)">${r.errors.length} refusé(s) : ${esc(r.errors.slice(0,3).join(' ; '))}</span>`:''} — `)},400)})};
inb.last=0;$('#ibrights').onchange=e=>api('/api/inbox/rights',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:e.target.checked})}).then(inb);
const AG={};const DAYS=10,MAXN=6;
const iso=d=>new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,10);
const agDays=()=>Array.from({length:DAYS},(_,i)=>{const d=new Date();d.setDate(d.getDate()+i);return d});
function agenda(){$('#agenda').innerHTML=agDays().map((d,i)=>{const k=iso(d),n=AG[k]||0;
  const lab=i===0?'Aujourd\'hui':i===1?'Demain':d.toLocaleDateString('fr-FR',{weekday:'short'});
  return `<div class="day${n?' on':''}"><small>${esc(lab)}</small><div class="d">${d.getDate()} ${esc(d.toLocaleDateString('fr-FR',{month:'short'}))}</div><div class="c"><button data-d="${k}" data-s="-1" aria-label="Moins">−</button><b>${n}</b><button data-d="${k}" data-s="1" aria-label="Plus">+</button></div></div>`}).join('');west()}
function west(){const n=Object.values(AG).reduce((a,b)=>a+b,0);const j=Object.values(AG).filter(x=>x>0).length;
  $('#west').textContent=n?`${n} vidéo${n>1?'s':''} sur ${j} jour${j>1?'s':''}. Compte environ ${n*4} minutes (3 à 4 par morceau). Chaque vidéo est envoyée à TikTok et YouTube dès qu'elle est montée, et programmée DANS chaque réseau à la date choisie (jusqu'à 10 jours). Ne touche pas au Mac pendant ce temps.`:'Clique sur + pour choisir le nombre de vidéos de chaque jour.';
  const per=formats.size>1?2:1,up=n*per;if(n&&up>YT_DAILY)$('#west').innerHTML+=`<br><b style="color:var(--bad)">⚠ YouTube limite à ${YT_DAILY} envois par jour</b> : ${n} vidéo${n>1?'s':''} × ${per} format${per>1?'s':''} = ${up} envois. ${YT_DAILY} partent aujourd'hui, les autres attendent (TikTok part tout de suite) et sont envoyées automatiquement quand YouTube le permet — <b>laisse la page ouverte</b>. Pour tout envoyer plus vite, décoche un format.`;
  $('#wgo').disabled=!n}
$('#agenda').onclick=e=>{const b=e.target.closest('[data-d]');if(!b)return;const k=b.dataset.d;AG[k]=Math.max(0,Math.min(MAXN,(AG[k]||0)+(+b.dataset.s)));agenda()};
document.querySelector('.quick').onclick=e=>{const b=e.target.closest('[data-quick]');if(!b)return;const v=+b.dataset.quick;agDays().forEach((d,i)=>{AG[iso(d)]=(i>=1&&i<=7)?v:0});agenda()};
agenda();
function watch(txt){$('#job').hidden=false;$('#log').textContent='';$('#res').innerHTML='';$('#err').hidden=true;since=0;cur=-1;fmtLabel='';stepper();$('#now').textContent=txt||'En cours…';
  $('#job').scrollIntoView({behavior:'smooth',block:'start'});if(!timer)timer=setInterval(poll,1500);poll()}
const wbody=()=>({days:Object.entries(AG).filter(([k,n])=>n>0).map(([date,count])=>({date,count})),times:$('#wtimes').value,immediate:$('#wnow').checked});
$('#wgo').onclick=()=>{const n=Object.values(AG).reduce((a,b)=>a+b,0);if(!n)return;if(!confirm('Fabriquer '+n+' vidéo'+(n>1?'s':'')+' puis les programmer ? Ne touche pas au Mac pendant la fabrication.'))return;
  const pend=PENDING_N;const rep=pend>0&&confirm(pend+' publication(s) sont déjà programmées. Les remplacer par ce nouvel agenda ? (OK = remplacer, Annuler = les garder en plus)');
  api('/api/week',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...wbody(),replace:rep,formats:[...formats],synthesia:$('#synth').checked,lang:$('#lang').value})})
   .then(r=>{if(r.error){$('#wmsg').textContent=r.error;return}$('#wmsg').textContent='';watch('Démarrage de la production…')})};
$('#wplan').onclick=()=>api('/api/schedule/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(wbody())})
  .then(r=>{if(r.error){$('#wmsg').textContent=r.error;return}$('#wmsg').textContent='';watch('Envoi des vidéos prêtes aux réseaux…')});
document.addEventListener('click',e=>{
  const ca=e.target.closest('[data-cancelall]');if(ca){if(confirm('Annuler les publications programmées DANS L\'APP ? (les vidéos et ce qui est programmé dans TikTok / YouTube ne sont pas touchés)'))api('/api/schedule/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({all:true})}).then(sched);return}
  const c=e.target.closest('[data-cancel]');if(c){api('/api/schedule/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:+c.dataset.cancel})}).then(sched);return}
  const n=e.target.closest('[data-now]');if(n){if(!confirm('Publier cette vidéo maintenant ? Ne touche ni à la souris ni au clavier pendant l\'envoi.'))return;
    api('/api/publish-now',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:+n.dataset.now})}).then(r=>{if(r.error){alert(r.error);return}watch('Publication en cours…')});return}
  const s=e.target.closest('[data-at]');if(s){const v=document.querySelector(`input[data-when="${s.dataset.at}"]`).value;if(!v){alert('Choisis d\'abord la date et l\'heure.');return}
    api('/api/schedule/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_ids:[+s.dataset.at],at:v})}).then(r=>{if(r.error){alert(r.error);return}watch('Envoi aux réseaux…')})}});
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
function bar(s){const p=s.progress,i=$('#bar i');if(s.status==='done'){i.className='det';i.style.width='100%';$('#pct').textContent='';return}
  if(!p||!p.count||s.status!=='running'){i.className='';i.style.width='';$('#pct').textContent='';return}
  const w=Math.max(3,Math.min(99,(p.done+p.pct/100)/p.count*100));i.className='det';i.style.width=w.toFixed(0)+'%';
  const age=p.t?Math.round(Date.now()/1000-p.t):0;$('#pct').textContent=`Vidéo ${Math.min(p.done+1,p.count)}/${p.count}`+(p.label?` · ${p.label}${p.pct?' '+Math.round(p.pct)+' %':''}`:'')+` · ${Math.round(w)} % du lot`}
function hl(){api('/api/health').then(h=>{if(h.error)return;const e=$('#health');
  e.innerHTML=`<b style="color:var(--ok)">${h.published}</b> envoyée${h.published>1?'s':''}`+(h.failed?` · <b style="color:var(--bad)">${h.failed} à vérifier</b>`:'')+`<br><small>disque : ${h.disk_gb} Go libres</small>`+(h.errors.length?`<br><small style="color:var(--bad)">${esc(h.errors[0].stage)} : ${esc(h.errors[0].message)}</small>`:'')})}
function ap(){api('/api/autopilot').then(a=>{if(a.error)return;$('#apon').checked=!!a.enabled;$('#apday').value=a.per_day;$('#apdays').value=a.days;
  $('#aplabel').textContent=a.enabled?'Pilote automatique activé':'Pilote automatique';$('#auto').classList.toggle('on',!!a.enabled);
  $('#apmsg').textContent=a.enabled?(a.message||'Vérification…'):'Désactivé : rien n\'est fabriqué tant que tu ne l\'actives pas.'})}
function apset(){api('/api/autopilot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:$('#apon').checked,per_day:+$('#apday').value,days:+$('#apdays').value})}).then(a=>{if(a.error)alert(a.error);ap()})}
['#apon','#apday','#apdays'].forEach(i=>$(i).onchange=apset);
function poll(){api('/api/status?since='+since).then(s=>{
  since=s.last;const L=$('#log');s.logs.forEach(l=>track(l));
  if(s.logs.length){L.textContent+=s.logs.join('\n')+'\n';L.scrollTop=L.scrollHeight;const last=s.logs[s.logs.length-1];$('#now').textContent=(fmtLabel&&s.status==='running'?fmtLabel+' · ':'')+last.replace(/\s*\[(vertical|horizontal)\]\s*/,' ').trim()}
  stepper();const run=s.status==='running';bar(s);$('#bar').hidden=!run;$('#stop').hidden=!run;$('#stoprec').hidden=!run||ENGINE!=='synthesia';if(run&&!$('#stoprec').dataset.busy){$('#stop').disabled=false;$('#stoprec').disabled=false};if(!run)delete $('#stoprec').dataset.busy;estimate();if(run){$('#go').disabled=true;$('#go').textContent='Création en cours…'}
  $('#chip').textContent=run?'En cours':s.status==='done'?'Terminé':s.status==='cancelled'?'Arrêté':'Échec';$('#chip').className='chip '+(s.status==='done'?'ok':s.status==='failed'||s.status==='cancelled'?'bad':'');
  if(!run){clearInterval(timer);timer=null;vids();info();sched();cur=s.status==='done'?5:cur;stepper();
    if(s.status==='cancelled'){$('#now').textContent='Création arrêtée'}
    if(s.status==='failed'){$('#err').hidden=false;$('#err').textContent=s.error}
    if(s.waiting&&s.waiting.length){$('#err').hidden=false;$('#err').innerHTML=($('#err').innerHTML||'')+'<b>⏳ En attente de la limite YouTube :</b><br>'+s.waiting.map(f=>esc(f)).join('<br>')}
    if(s.failures&&s.failures.length){$('#err').hidden=false;$('#err').innerHTML='<b>Ce qui n\'a pas marché :</b><br>'+s.failures.map(f=>'✖ '+esc(f)).join('<br>')+'<br><small>Captures de chaque étape : dossier data/debug/steps · liste des boutons vus : data/debug/*_page.txt</small>'}
    if(s.planned&&s.planned.length){const f=s.planned[0];$('#now').innerHTML=`🗓 <b>${new Set(s.planned.map(p=>p.run_at)).size} vidéo(s) programmée(s) dans TikTok et YouTube</b> — la première sera en ligne ${esc(dfmt(f.run_at))}. Tu peux éteindre le Mac : les réseaux publient eux-mêmes.`;results(Array.isArray(s.result)?{videos:s.result.flatMap(r=>r.videos||[r])}:s.result);tab('home',true)}
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
api('/api/options').then(o=>{opts=o;$('#maxrec').value=o.max_record_seconds;YT_DAILY=o.youtube_daily||4;$('#lang').innerHTML=o.languages.map(l=>`<option value="${l.key}"${l.key===o.default_language?' selected':''}>${l.label}</option>`).join('');$('#tc').innerHTML=o.countries.map(c=>`<option value="${c.key}">${c.label}</option>`).join('');level=(o.levels[1]||o.levels[0]).key;formats=new Set(o.default_formats);render()});
info();vids();songs();sched();inb();ap();setInterval(ap,15000);hl();setInterval(hl,30000);setInterval(info,20000);setInterval(sched,30000);setInterval(inb,10000);
api('/api/status').then(s=>{if(s.status==='running'){$('#job').hidden=false;since=0;timer=setInterval(poll,1500);poll()}});
</script></div></body></html>
"""
