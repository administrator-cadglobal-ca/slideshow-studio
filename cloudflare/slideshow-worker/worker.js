/**
 * Slideshow Studio — Cloudflare Worker
 * Serves public slideshow player from R2 + validates tokens from D1
 *
 * Routes:
 *   GET  /s/<token>                  → HTML player page
 *   GET  /s/<token>/frames/<file>    → frame/thumbnail from R2
 *   GET  /s/<token>/audio/<file>     → audio clip from R2
 *   GET  /s/<token>/clips/<labelId>  → clip list JSON
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS headers for API calls
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // Route: /s/<token>/<...rest>
    const match = path.match(/^\/s\/([a-zA-Z0-9_-]+)(\/.*)?$/);
    if (!match) {
      return new Response('Not found', { status: 404 });
    }

    const token = match[1];
    const rest  = match[2] || '';

    // ── Validate token from D1 ────────────────────────────────────────────────
    const row = await env.DB.prepare(
      `SELECT * FROM slideshow_tokens WHERE token = ? AND (expires_at IS NULL OR expires_at > datetime('now'))`
    ).bind(token).first();

    if (!row) {
      return new Response(renderError('Link expired or not found'), {
        status: 410, headers: { 'Content-Type': 'text/html' }
      });
    }

    // Update usage stats (fire and forget)
    ctx.waitUntil(
      env.DB.prepare(
        `UPDATE slideshow_tokens SET use_count = use_count + 1, last_used_at = datetime('now') WHERE token = ?`
      ).bind(token).run()
    );

    const projectId = row.project_id;
    const userId    = row.user_id;

    // ── Password check (only for main player page) ────────────────────────────
    if (row.password_hash && rest === '') {
      const urlParams = new URL(request.url).searchParams;
      const submitted = urlParams.get('pwd');
      if (!submitted) {
        return new Response(renderPasswordPage(token), {
          headers: { 'Content-Type': 'text/html; charset=utf-8' }
        });
      }
      // Verify SHA-256 hash
      const encoder    = new TextEncoder();
      const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(submitted));
      const hashHex    = Array.from(new Uint8Array(hashBuffer))
                              .map(b => b.toString(16).padStart(2,'0')).join('');
      if (hashHex !== row.password_hash) {
        return new Response(renderPasswordPage(token, true), {
          headers: { 'Content-Type': 'text/html; charset=utf-8' }
        });
      }
    }

    // ── Route: serve frame — /frames/<version>/<file> or /frames/<file> ────────
    if (rest.startsWith('/frames/')) {
      const parts   = rest.replace('/frames/', '').split('/');
      // New format: /frames/<version>/<file>
      // Old format: /frames/<file>
      let r2Key;
      if (parts.length >= 2) {
        r2Key = `${userId}/${projectId}/${parts[0]}/${parts.slice(1).join('/')}`;
      } else {
        r2Key = `${userId}/${projectId}/frames/${parts[0]}`;
      }
      const obj = await env.BUCKET.get(r2Key);
      if (!obj) return new Response('Not found', { status: 404 });
      return new Response(obj.body, {
        headers: {
          'Content-Type': 'image/jpeg',
          'Cache-Control': 'public, max-age=86400',
          ...corsHeaders
        }
      });
    }

    // ── Route: serve audio ────────────────────────────────────────────────────
    if (rest.startsWith('/audio/')) {
      const file  = rest.replace('/audio/', '');
      const r2Key = `${userId}/${projectId}/audio/${file}`;
      const obj   = await env.BUCKET.get(r2Key);
      if (!obj) return new Response('Not found', { status: 404 });
      return new Response(obj.body, {
        headers: {
          'Content-Type': 'audio/mpeg',
          'Cache-Control': 'public, max-age=86400',
          'Accept-Ranges': 'bytes',
          ...corsHeaders
        }
      });
    }

    // ── Route: clips JSON ─────────────────────────────────────────────────────
    if (rest.startsWith('/clips/')) {
      const labelId = rest.replace('/clips/', '');
      const clipsRow = await env.DB.prepare(
        `SELECT clips_json FROM slideshow_clips WHERE token = ? AND label_id = ?`
      ).bind(token, labelId).first();
      if (!clipsRow) return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      return new Response(clipsRow.clips_json, {
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    // ── Route: main player page ───────────────────────────────────────────────
    const meta = JSON.parse(row.meta_json || '{}');
    return new Response(renderPlayer(token, row, meta), {
      headers: { 'Content-Type': 'text/html; charset=utf-8' }
    });
  }
};

// ── Player HTML ───────────────────────────────────────────────────────────────
function renderPlayer(token, row, meta) {
  const title      = meta.project_name || 'Slideshow';
  const labels     = meta.labels || [];
  const defaultLabelId = meta.default_label_id || '';
  // Support both new format (versions dict) and old format (frames array)
  const versions   = meta.versions || {};
  const verKeys    = Object.keys(versions);
  const defVersion = meta.default_version ||
    verKeys.find(v => v === 'hd-landscape') ||
    verKeys.find(v => v && v.startsWith('hd')) ||
    verKeys[0] || 'hd-landscape';
  const frames     = versions[defVersion] || meta.frames || [];

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title>${escHtml(title)}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#000;height:100vh;width:100vw;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}

/* Stage fills everything */
.stage{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:#000}
.stage img{width:100%;height:100%;object-fit:contain;transition:opacity .35s}
.stage img.fade{opacity:0}

/* All controls overlay the photo */
.overlay{position:fixed;inset:0;z-index:10;pointer-events:none;transition:opacity .4s}
.overlay.hidden{opacity:0}

/* Top bar: title + selectors */
.top-bar{position:absolute;top:0;left:0;right:0;padding:12px 16px;display:flex;align-items:center;gap:10px;background:linear-gradient(to bottom,rgba(0,0,0,.7) 0%,transparent 100%);pointer-events:all}
.proj-title{color:#fff;font-size:14px;font-weight:700;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sel{background:rgba(0,0,0,.5);border:1px solid rgba(255,255,255,.3);color:#fff;border-radius:6px;padding:4px 8px;font-size:11px;outline:none;backdrop-filter:blur(4px)}

/* Bottom controls */
.bot-bar{position:absolute;bottom:0;left:0;right:0;padding:10px 16px 16px;background:linear-gradient(to top,rgba(0,0,0,.75) 0%,transparent 100%);pointer-events:all}
.prog{width:100%;height:3px;background:rgba(255,255,255,.25);border-radius:2px;margin-bottom:12px;cursor:pointer}
.prog-fill{height:100%;background:#fff;border-radius:2px;width:0%;transition:width .3s}
.ctrl-row{display:flex;align-items:center;justify-content:center;gap:10px}
.btn{background:rgba(255,255,255,.15);border:none;color:#fff;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);transition:.15s}
.btn:hover{background:rgba(255,255,255,.3)}
.btn.sm{width:36px;height:36px;font-size:14px}
.btn.lg{width:50px;height:50px;font-size:22px;background:rgba(255,255,255,.25)}
.btn.lg:hover{background:rgba(255,255,255,.4)}
.sep{width:1px;height:28px;background:rgba(255,255,255,.2);margin:0 4px}
.song{font-size:11px;color:rgba(255,255,255,.8);max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ctr{font-size:11px;color:rgba(255,255,255,.6);min-width:46px;text-align:center}

/* Fullscreen button top-right */
.fs-btn{position:absolute;top:12px;right:12px;pointer-events:all}
</style>
</head>
<body>

<div class="stage">
  <img id="img" alt="">
</div>

<div class="overlay" id="overlay">
  <!-- Top bar -->
  <div class="top-bar">
    <span class="proj-title">${escHtml(title)}</span>
    ${Object.keys(versions).length > 1 ? `
    <select class="sel" onchange="switchVersion(this.value)">
      ${Object.keys(versions).sort(function(a,b){
        const o=['hd-landscape','hd-portrait','sd-landscape','sd-portrait','2k-landscape','2k-portrait','4k-landscape','4k-portrait'];
        return o.indexOf(a)-o.indexOf(b);
      }).map(v=>'<option value="'+v+'" '+(v===defVersion?'selected':'')+'>'+v.replace('-',' ').toUpperCase()+'</option>').join('')}
    </select>` : ''}
    ${labels.length ? `
    <select class="sel" onchange="switchLabel(this.value)">
      <option value="">🔇 No music</option>
      ${labels.map(l=>'<option value="'+l.id+'" '+(l.id==defaultLabelId?'selected':'')+'>'+escHtml(l.name)+'</option>').join('')}
    </select>` : ''}
    <button class="btn sm fs-btn" onclick="toggleFs()" title="Fullscreen">⛶</button>
  </div>

  <!-- Bottom controls -->
  <div class="bot-bar">
    <div class="prog" onclick="seek(event,this)"><div class="prog-fill" id="pf"></div></div>
    <div class="ctrl-row">
      <span class="ctr" id="ctr">1 / 1</span>
      <button class="btn sm" onclick="go(-1)">◀</button>
      <button class="btn lg" id="pb" onclick="togglePlay()">▶</button>
      <button class="btn sm" onclick="go(1)">▶</button>
      <div class="sep"></div>
      <button class="btn sm" onclick="prevSong()">⏮</button>
      <button class="btn sm" id="ab" onclick="toggleAudio()">🔇</button>
      <button class="btn sm" onclick="nextSong()">⏭</button>
      <span class="song" id="sn">—</span>
    </div>
  </div>
</div>

<audio id="aud"></audio>

<script>
var TOKEN    = ${JSON.stringify(token)};
var VERSIONS = ${JSON.stringify(versions)};
var CUR_VER  = ${JSON.stringify(defVersion)};
var FRAMES   = ${JSON.stringify(frames)};
if(!Object.keys(VERSIONS).length && FRAMES.length){
  VERSIONS={'hd-landscape':FRAMES}; CUR_VER='hd-landscape';
}
var SONGS=[], si=0, ii=0, playing=false, timer=null, DUR=4000;
var aud=document.getElementById('aud');
var overlay=document.getElementById('overlay');
var hideTimer=null;

// ── Controls auto-hide ────────────────────────────────────────────────────────
function showControls(){
  overlay.classList.remove('hidden');
  clearTimeout(hideTimer);
  hideTimer=setTimeout(function(){ overlay.classList.add('hidden'); }, 3000);
}
document.addEventListener('mousemove', showControls);
document.addEventListener('touchstart', showControls, {passive:true});
document.addEventListener('keydown', showControls);
showControls();

// ── Photo ─────────────────────────────────────────────────────────────────────
function showImg(idx){
  if(!FRAMES.length) return;
  idx=Math.max(0,Math.min(idx,FRAMES.length-1)); ii=idx;
  var el=document.getElementById('img');
  el.classList.add('fade');
  setTimeout(function(){
    el.src=Object.keys(VERSIONS).length?'/s/'+TOKEN+'/frames/'+CUR_VER+'/'+FRAMES[idx]:'/s/'+TOKEN+'/frames/'+FRAMES[idx];
    el.classList.remove('fade');
  },180);
  document.getElementById('ctr').textContent=(idx+1)+' / '+FRAMES.length;
  document.getElementById('pf').style.width=(FRAMES.length>1?(idx/(FRAMES.length-1)*100):0)+'%';
}
function go(d){ var n=ii+d; if(n<0||n>=FRAMES.length)return; showImg(n); if(playing)resetT(); }
function togglePlay(){ playing?stop():start(); }
function start(){ playing=true; document.getElementById('pb').textContent='⏸'; resetT(); }
function stop(){ playing=false; document.getElementById('pb').textContent='▶'; clearTimeout(timer); }
function resetT(){ clearTimeout(timer); timer=setTimeout(function(){ if(ii+1<FRAMES.length)go(1); else stop(); },DUR); }
function seek(e,bar){ showImg(Math.round((e.offsetX/bar.offsetWidth)*(FRAMES.length-1))); }
function switchVersion(ver){ CUR_VER=ver; FRAMES=VERSIONS[ver]||[]; ii=0; if(FRAMES.length)showImg(0); }

// ── Audio ─────────────────────────────────────────────────────────────────────
function switchLabel(id){
  var wasPlaying=!aud.paused; aud.pause(); SONGS=[]; si=0;
  if(!id){ aud.src=''; updateSong(); document.getElementById('ab').textContent='🔇'; return; }
  fetch('/s/'+TOKEN+'/clips/'+id).then(function(r){return r.json();}).then(function(d){
    SONGS=Array.isArray(d)?d:(d.clips||d); si=0;
    if(SONGS.length){
      aud.src='/s/'+TOKEN+'/audio/'+SONGS[0].file;
      aud.currentTime=SONGS[0].start||0; updateSong();
      if(wasPlaying || !_audioStarted){
        aud.play().then(function(){
          document.getElementById('ab').textContent='🔊';
          _audioStarted = true;
        }).catch(function(){});
      }
    } else { aud.src=''; updateSong(); }
  });
}
function loadSong(idx){
  if(!SONGS.length)return;
  si=Math.max(0,Math.min(idx,SONGS.length-1));
  aud.src='/s/'+TOKEN+'/audio/'+SONGS[si].file;
  aud.currentTime=SONGS[si].start||0; updateSong();
}
function toggleAudio(){
  if(!SONGS.length)return;
  if(aud.paused){ aud.play(); document.getElementById('ab').textContent='🔊'; }
  else { aud.pause(); document.getElementById('ab').textContent='🔇'; }
}
function prevSong(){
  var w=!aud.paused; loadSong(si-1);
  if(w){ aud.play().catch(function(){}); document.getElementById('ab').textContent='🔊'; }
}
function nextSong(){
  var w=!aud.paused; loadSong(si+1<SONGS.length?si+1:0);
  if(w){ aud.play().catch(function(){}); document.getElementById('ab').textContent='🔊'; }
}
function updateSong(){ document.getElementById('sn').textContent=SONGS.length&&SONGS[si]?'♪ '+SONGS[si].name:'—'; }
aud.onended=function(){ si+1<SONGS.length?nextSong():loadSong(0); };
aud.ontimeupdate=function(){
  var s=SONGS[si]; if(s&&s.end&&aud.currentTime>=s.end){ si+1<SONGS.length?nextSong():loadSong(0); }
};

// ── Fullscreen ────────────────────────────────────────────────────────────────
function toggleFs(){
  if(!document.fullscreenElement) document.documentElement.requestFullscreen().catch(function(){document.body.requestFullscreen();});
  else document.exitFullscreen();
}

// ── Keyboard ──────────────────────────────────────────────────────────────────
document.addEventListener('keydown',function(e){
  if(e.key==='ArrowRight') go(1);
  else if(e.key==='ArrowLeft') go(-1);
  else if(e.key===' '){ e.preventDefault(); togglePlay(); }
  else if(e.key==='f') toggleFs();
  else if(e.key==='m') toggleAudio();
});

// ── Init ──────────────────────────────────────────────────────────────────────
if(FRAMES.length) showImg(0);
var defLabel=${JSON.stringify(String(defaultLabelId))};

// Auto-start slideshow
if(FRAMES.length > 1) start();

// Auto-start audio — browsers require user gesture first
// So we start on first interaction if not already playing
var _audioStarted = false;
function tryStartAudio(){
  if(_audioStarted || !SONGS.length) return;
  _audioStarted = true;
  aud.play().then(function(){
    document.getElementById('ab').textContent='🔊';
  }).catch(function(){});
}
document.addEventListener('click', tryStartAudio, {once:false, passive:true});
document.addEventListener('keydown', tryStartAudio, {once:false, passive:true});
document.addEventListener('touchstart', tryStartAudio, {once:false, passive:true});

if(defLabel) switchLabel(defLabel);
</script>
</body>
</html>`
}

function renderPasswordPage(token, failed) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Password Required</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:20px}
.box{background:#1e293b;border-radius:14px;padding:32px;width:320px;max-width:90vw;text-align:center}
h2{font-size:18px;margin-bottom:8px}
p{font-size:13px;color:#94a3b8;margin-bottom:20px}
input{width:100%;background:#0f172a;border:1px solid #334155;color:#fff;border-radius:8px;
  padding:10px 14px;font-size:16px;outline:none;text-align:center;letter-spacing:3px;margin-bottom:12px}
input:focus{border-color:#3b82f6}
button{width:100%;background:#1d4ed8;color:#fff;border:none;border-radius:8px;padding:10px;
  font-size:14px;font-weight:600;cursor:pointer}
button:hover{background:#2563eb}
.err{color:#f87171;font-size:12px;margin-bottom:8px}
.icon{font-size:40px;margin-bottom:4px}
</style>
</head>
<body>
<div class="box">
  <div class="icon">🔒</div>
  <h2>Password Required</h2>
  <p>This slideshow is password protected.</p>
  ${failed ? '<div class="err">Incorrect password. Please try again.</div>' : ''}
  <form method="GET" action="/s/${token}">
    <input type="password" name="pwd" placeholder="Enter password" autofocus>
    <button type="submit">View Slideshow →</button>
  </form>
</div>
</body>
</html>`;
}

function renderError(msg) {
  return `<!DOCTYPE html><html><body style="background:#0f172a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px">
<div style="font-size:48px">🔗</div>
<h1 style="font-size:20px">${escHtml(msg)}</h1>
<p style="color:#64748b;font-size:13px">The link may have expired or been revoked.</p>
</body></html>`;
}

function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
