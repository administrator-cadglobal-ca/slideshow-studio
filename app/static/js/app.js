// ── Toast notifications ─────────────────────────────────────────────────────────
function showToast(msg, type) {
  type = type || 'info';
  var colors = {success:'#059669', error:'#dc2626', info:'#1e3a52', warning:'#d97706'};
  var t = document.createElement('div');
  t.textContent = msg;
  t.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:99999;' +
    'background:' + (colors[type]||colors.info) + ';color:#fff;' +
    'padding:10px 18px;border-radius:8px;font-size:13px;font-weight:500;' +
    'box-shadow:0 4px 12px rgba(0,0,0,.2);opacity:0;transition:opacity .2s;max-width:320px';
  document.body.appendChild(t);
  setTimeout(function(){ t.style.opacity='1'; }, 10);
  setTimeout(function(){ t.style.opacity='0'; setTimeout(function(){ t.remove(); }, 200); }, 3000);
}

// ── Modal helpers ───────────────────────────────────────────────────────────────
function openModal(id) {
  var el = document.getElementById(id);
  if(el){ el.classList.add('open'); el.style.display = 'flex'; }
}
function closeModal(id) {
  var el = document.getElementById(id);
  if(el){ el.classList.remove('open'); el.style.display = 'none'; }
}

// ── User menu ──────────────────────────────────────────────────────────────────
function toggleUserMenu() {
  document.getElementById('userDropdown')?.classList.toggle('open');
}
document.addEventListener('click', function(e) {
  const wrap = document.querySelector('.nav-user-wrap');
  const drop = document.getElementById('userDropdown');
  if (drop && wrap && !wrap.contains(e.target)) drop.classList.remove('open');
});

// ── Dismiss banner ─────────────────────────────────────────────────────────────
function dismissBanner() {
  const b = document.getElementById('pendingBanner');
  if (b) { b.style.opacity='0'; setTimeout(()=>b.remove(),300); }
}

// ── Auto-dismiss flash messages ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });
});

// ── Tabs ───────────────────────────────────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-tab="'+tabId+'"')?.classList.add('active');
  document.getElementById(tabId)?.classList.add('active');
  history.replaceState(null,'','#'+tabId);
}
document.addEventListener('DOMContentLoaded', function() {
  const hash = location.hash.replace('#','');
  if (hash && document.getElementById(hash)) switchTab(hash);
  else {
    const first = document.querySelector('.tab-btn');
    if (first) switchTab(first.dataset.tab);
  }
});

// ── Registration reject toggle ─────────────────────────────────────────────────
function toggleReject(id) {
  const el = document.getElementById('reject-' + id);
  if (!el) return;
  const open = el.style.display !== 'none';
  el.style.display = open ? 'none' : 'block';
  if (!open) el.querySelector('input')?.focus();
}

// ── History accordion ──────────────────────────────────────────────────────────
function toggleHistory() {
  const list = document.getElementById('historyList');
  const icon = document.getElementById('historyIcon');
  if (!list) return;
  const open = list.style.display !== 'none';
  list.style.display = open ? 'none' : 'block';
  if (icon) icon.style.transform = open ? '' : 'rotate(180deg)';
}

// ── Modal helpers ──────────────────────────────────────────────────────────────
function openModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.add('open'); m.querySelector('input')?.focus(); }
}
function closeModal(id) {
  document.getElementById(id)?.classList.remove('open');
}
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') document.querySelectorAll('.modal-overlay.open')
    .forEach(m => m.classList.remove('open'));
});

// ── Quota modal ────────────────────────────────────────────────────────────────
function openQuota(userId, name, gb) {
  document.getElementById('quotaName').textContent = name;
  document.getElementById('quotaInput').value = gb;
  document.getElementById('quotaForm').action = '/admin/users/'+userId+'/quota';
  openModal('quotaModal');
}

// ── OTP input — auto uppercase ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  const otp = document.getElementById('otpInput');
  if (otp) {
    otp.addEventListener('input', function() {
      const pos = this.selectionStart;
      this.value = this.value.toUpperCase().replace(/[^A-Z0-9]/g,'');
      this.setSelectionRange(pos, pos);
    });
  }
});

// ── Global photo upload handler (called directly from onchange) ──────────────
function handlePhotoUpload(input) {
  console.log('[UPLOAD] handlePhotoUpload called, files:', input.files.length);
  if (!input.files.length) return;
  const zone = document.getElementById('uploadZone');
  const projectId = zone ? zone.dataset.project : null;
  if (!projectId) { alert('Project ID missing'); return; }
  _doPhotoUpload(input.files, projectId, zone);
}

function _doPhotoUpload(files, projectId, zone) {
  // Show progress
  let progEl = document.getElementById('photoUploadProgress');
  if (!progEl) {
    progEl = document.createElement('div');
    progEl.id = 'photoUploadProgress';
    progEl.style.cssText = 'background:#fff;border:1px solid #1e3a52;border-radius:8px;padding:16px 20px;margin-bottom:12px;text-align:center';
    if (zone) zone.parentNode.insertBefore(progEl, zone);
    else document.querySelector('.tab-panel.active').prepend(progEl);
  }
  const total = files.length;
  progEl.innerHTML =
    '<div style="font-size:13px;font-weight:600;margin-bottom:10px;color:#1e3a52" id="upStatus">Uploading ' + total + ' photo' + (total>1?'s':'') + '...</div>' +
    '<div style="background:#e8e5e0;border-radius:20px;height:10px;overflow:hidden;margin:0 auto;max-width:400px">' +
      '<div id="upBar" style="height:100%;width:0%;background:#1e3a52;border-radius:20px;transition:width .3s"></div>' +
    '</div>' +
    '<div id="upCount" style="font-size:11px;color:#9ca3af;margin-top:8px">0 / ' + total + '</div>';
  if (zone) { zone.style.opacity='0.4'; zone.style.pointerEvents='none'; }

  const BATCH = 5;
  let uploaded = 0, skipped = 0;
  const allFiles = Array.from(files);

  async function run() {
    for (let i = 0; i < allFiles.length; i += BATCH) {
      const batch = allFiles.slice(i, i + BATCH);
      const fd = new FormData();
      batch.forEach(f => fd.append('photos', f));
      try {
        console.log('[UPLOAD] posting batch', Math.floor(i/BATCH)+1);
        const r = await fetch('/api/v1/projects/'+projectId+'/photos/upload', {
          method: 'POST', body: fd
        });
        console.log('[UPLOAD] status:', r.status);
        const d = await r.json();
        console.log('[UPLOAD] result:', d);
        uploaded += d.uploaded || 0;
        skipped  += d.skipped  || 0;
        if (d.errors && d.errors.length) console.warn('[UPLOAD] errors:', d.errors);
      } catch(e) {
        console.error('[UPLOAD] batch error:', e);
      }
      const done = Math.min(i + BATCH, allFiles.length);
      const pct  = Math.round(done / allFiles.length * 100);
      const bar  = document.getElementById('upBar');
      const cnt  = document.getElementById('upCount');
      const sta  = document.getElementById('upStatus');
      if (bar) bar.style.width = pct + '%';
      if (cnt) cnt.textContent = done + ' / ' + allFiles.length + ' photos';
      if (sta) sta.textContent = 'Uploading... ' + pct + '%';
    }
    // Done
    const sta = document.getElementById('upStatus');
    const bar = document.getElementById('upBar');
    if (sta) sta.textContent = '✓ ' + uploaded + ' photo' + (uploaded!==1?'s':'') + ' uploaded!';
    if (bar) { bar.style.width='100%'; bar.style.background='#059669'; }
    if (zone) { zone.style.opacity=''; zone.style.pointerEvents=''; }
    var msg = uploaded + ' photo' + (uploaded!==1?'s':'') + ' uploaded';
    if (skipped) msg += ', ' + skipped + ' duplicate' + (skipped!==1?'s':'') + ' skipped';
    showToast(msg, 'success');
    console.log('[UPLOAD] complete, uploaded=' + uploaded);
    // Show refresh button - more reliable than JS navigation in Brave
    var staEl = document.getElementById('upStatus');
    if (staEl) {
      staEl.innerHTML = '<span style="color:#059669;font-weight:700">✓ ' + uploaded + ' photo' + (uploaded!==1?'s':'') + ' uploaded!</span>' +
        ' &nbsp;<a href="' + window.location.pathname + '" style="background:#1e3a52;color:#fff;padding:5px 14px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600">↻ Show photos</a>';
    }
  }
  run().catch(function(e){ console.error('[UPLOAD] run() error:', e); showToast('Upload error: ' + e.message, 'error'); });
}

// ── Photo upload drag & drop ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  const zone = document.getElementById('uploadZone');
  const input = document.getElementById('photoInput');
  if (!zone || !input) return;

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
  });
  // change event handled by onchange attribute on input element

  function handleFiles(files) {
    if (!files.length) return;
    const projectId = zone.dataset.project;

    // Show progress overlay above the zone
    let progEl = document.getElementById('photoUploadProgress');
    if (!progEl) {
      progEl = document.createElement('div');
      progEl.id = 'photoUploadProgress';
      progEl.style.cssText = 'background:#fff;border:1px solid #e8e5e0;border-radius:8px;padding:16px 20px;margin-bottom:12px;text-align:center';
      zone.parentNode.insertBefore(progEl, zone);
    }
    progEl.innerHTML = '      <div style="font-size:13px;font-weight:600;margin-bottom:10px;color:#1e3a52" id="upStatus">        Uploading ${files.length} photo${files.length>1?"s":""}...      </div>      <div style="background:#e8e5e0;border-radius:20px;height:10px;overflow:hidden;margin:0 auto;max-width:400px">        <div id="upBar" style="height:100%;width:0%;background:#1e3a52;border-radius:20px;transition:width .3s"></div>      </div>      <div id="upCount" style="font-size:11px;color:#9ca3af;margin-top:8px">0 / ${files.length} photos</div>';
    zone.style.opacity = '0.4';
    zone.style.pointerEvents = 'none';

    // Upload in batches of 5 for better progress feedback
    const BATCH = 5;
    let uploaded = 0, errors = [];
    const allFiles = Array.from(files);

    async function uploadBatch(batch) {
      const fd = new FormData();
      batch.forEach(f => fd.append('photos', f));
      const r = await fetch('/api/v1/projects/' + projectId + '/photos/upload', {
        method: 'POST', body: fd
      });
      return r.json();
    }

    async function runUploads() {
      for (let i = 0; i < allFiles.length; i += BATCH) {
        const batch = allFiles.slice(i, i + BATCH);
        try {
          const data = await uploadBatch(batch);
          uploaded += data.uploaded || 0;
        } catch(e) {
          console.error('batch error:', e);
        }
        const done = Math.min(i + BATCH, allFiles.length);
        const pct  = Math.round(done / allFiles.length * 100);
        const bar  = document.getElementById('upBar');
        const cnt  = document.getElementById('upCount');
        const sta  = document.getElementById('upStatus');
        if (bar) bar.style.width = pct + '%';
        if (cnt) cnt.textContent = done + ' / ' + allFiles.length;
        if (sta) sta.textContent = 'Uploading... ' + pct + '%';
      }
      const sta = document.getElementById('upStatus');
      const bar = document.getElementById('upBar');
      if (sta) sta.textContent = uploaded + (uploaded !== 1 ? ' photos' : ' photo') + ' uploaded!';
      if (bar) { bar.style.width = '100%'; bar.style.background = '#059669'; }
      if (zone) { zone.style.opacity = ''; zone.style.pointerEvents = ''; }
      setTimeout(function() { location.reload(); }, 900);
    }

    runUploads();
  }
});
