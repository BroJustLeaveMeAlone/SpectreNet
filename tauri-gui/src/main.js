'use strict';

// ── Tauri bridge (graceful fallback when running in browser) ──────────────────
let invoke;
try {
  const tauri = window.__TAURI__;
  invoke = tauri ? tauri.core.invoke : async (cmd, args) => {
    if (cmd === 'server_url') return 'http://localhost:8888';
    if (cmd === 'ping_server') return true;
  };
} catch {
  invoke = async (cmd) => {
    if (cmd === 'server_url') return 'http://localhost:8888';
    return null;
  };
}

// ── State ─────────────────────────────────────────────────────────────────────
let SERVER = 'http://localhost:8888';
let opName = '';
let sse = null;

// ── Helpers ───────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const ts = iso => (iso || '').slice(11, 16);
const tsDate = iso => (iso || '').slice(0, 16).replace('T', ' ');

function show(id)  { $(id).style.display = ''; }
function hide(id)  { $(id).style.display = 'none'; }
function flex(id)  { $(id).style.display = 'flex'; }

function toast(msg, ms = 3500) {
  const el = $('toast');
  el.textContent = msg;
  el.style.display = 'block';
  clearTimeout(el._t);
  el._t = setTimeout(() => el.style.display = 'none', ms);
}

// ── API ───────────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const url = SERVER + path;
  const r = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  }).catch(() => null);
  if (!r) return null;
  return r.json().catch(() => null);
}

// ── Connection check + offline screen ─────────────────────────────────────────
async function retryConnect() {
  $('retry-status').textContent = 'Checking…';
  const ok = await api('GET', '/api/sessions').then(d => !!d);
  if (ok) {
    hide('offline-screen');
    flex('join-overlay');
  } else {
    $('retry-status').textContent = 'Still offline — is `snet server` running?';
  }
}

async function boot() {
  SERVER = await invoke('server_url').catch(() => 'http://localhost:8888');
  const ok = await api('GET', '/api/sessions').then(d => !!d);
  if (!ok) {
    show('offline-screen');
  } else {
    hide('offline-screen');
    flex('join-overlay');
  }
}

// ── Operator join / leave ──────────────────────────────────────────────────────
async function joinOp() {
  const name = $('join-name').value.trim();
  if (!name) return;
  await api('POST', '/api/operators/join', { name });
  opName = name;
  $('op-name-display').textContent = name;
  hide('join-overlay');
  flex('app');
  loadAll();
  connectSSE();
}

async function leaveOp() {
  if (!opName) return;
  await api('POST', '/api/operators/leave', { name: opName });
  opName = '';
  hide('app');
  flex('join-overlay');
  if (sse) { sse.close(); sse = null; }
}

$('join-name').addEventListener('keydown', e => { if (e.key === 'Enter') joinOp(); });

// ── Tabs ──────────────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === name);
  });
  document.querySelectorAll('.pane').forEach(p => {
    p.classList.toggle('active', p.id === `pane-${name}`);
  });
}

// ── Data loaders ──────────────────────────────────────────────────────────────
async function loadAll() {
  await Promise.all([loadSessions(), loadTargets(), loadLoot(), loadNotes(), loadOperators()]);
}

async function loadSessions() {
  const d = await api('GET', '/api/sessions');
  const sessions = d?.sessions || [];
  $('tc-sessions').textContent = sessions.length;
  const el = $('sessions-list');
  if (!sessions.length) { el.innerHTML = '<div class="empty">No active sessions</div>'; return; }
  el.innerHTML = sessions.map(s => `
    <div class="data-row">
      <span class="badge b-green">#${s.id}</span>
      <div class="row-body">
        <div class="row-title" style="font-family:monospace">${s.host}</div>
        <div class="row-meta">${s.platform} · ${s.user || '?'} · pid ${s.pid || '?'}</div>
        <div class="row-meta">${tsDate(s.opened)}</div>
      </div>
      <button class="btn-danger" onclick="killSession(${s.id})">Kill</button>
    </div>`).join('');
}

async function loadTargets() {
  const d = await api('GET', '/api/targets');
  const targets = d?.targets || [];
  $('tc-targets').textContent = targets.length;
  const el = $('targets-list');
  if (!targets.length) { el.innerHTML = '<div class="empty">No targets in scope</div>'; return; }
  el.innerHTML = targets.map(t => `
    <div class="data-row">
      <span class="badge b-cyan">scope</span>
      <div class="row-body" style="font-family:monospace">${t}</div>
    </div>`).join('');
}

async function loadLoot() {
  const d = await api('GET', '/api/loot');
  const loot = d?.loot || [];
  $('tc-loot').textContent = loot.length;
  const el = $('loot-list');
  if (!loot.length) { el.innerHTML = '<div class="empty">Loot vault empty</div>'; return; }
  const cls = { cred: 'b-red', hash: 'b-yellow', secret: 'b-yellow', file: 'b-cyan' };
  el.innerHTML = [...loot].reverse().slice(0, 60).map(e => `
    <div class="data-row">
      <span class="badge ${cls[e.type] || 'b-grey'}">${e.type}</span>
      <div class="row-body">
        <div class="row-title" style="font-size:12px;font-family:monospace">${e.text}</div>
        <div class="row-meta">${e.operator} · ${tsDate(e.t)}</div>
      </div>
    </div>`).join('');
}

async function loadNotes() {
  const d = await api('GET', '/api/notes');
  const notes = d?.notes || [];
  $('tc-notes').textContent = notes.length;
  const el = $('notes-list');
  if (!notes.length) { el.innerHTML = '<div class="empty">No notes</div>'; return; }
  el.innerHTML = [...notes].reverse().slice(0, 60).map(n => `
    <div class="data-row">
      <div class="row-body">
        <div class="row-title">${n.text}</div>
        <div class="row-meta">${n.operator} · ${tsDate(n.t)}</div>
      </div>
    </div>`).join('');
}

async function loadOperators() {
  const d = await api('GET', '/api/operators');
  const operators = d?.operators || [];
  const claims   = d?.claims || {};
  $('op-count').textContent = operators.length;

  $('op-list').innerHTML = operators.length
    ? operators.map(op => `
        <div class="op-card">
          <div class="op-card-head">
            <div class="dot dot-live"></div>
            <span class="op-card-name">${op.name}</span>
            ${op.name === opName ? '<span class="op-you">(you)</span>' : ''}
          </div>
          ${op.active_target ? `<div class="op-target">◎ ${op.active_target}</div>` : ''}
        </div>`).join('')
    : '<div class="empty" style="font-size:11px">No operators online</div>';

  const claimEntries = Object.entries(claims);
  $('claims-list').innerHTML = claimEntries.length
    ? claimEntries.map(([target, op]) => `
        <div class="claim-row">
          <span class="claim-op">${op}</span>
          <span class="muted">→</span>
          <span class="claim-target-name">${target}</span>
          ${op === opName
            ? `<button class="btn-danger" style="margin-left:auto;padding:1px 6px;font-size:10px" onclick="releaseTarget('${target}')">✕</button>`
            : ''}
        </div>`).join('')
    : '<div class="empty" style="font-size:11px">No active claims</div>';
}

// ── Actions ───────────────────────────────────────────────────────────────────
async function claimTarget() {
  const target = $('claim-input').value.trim();
  if (!target || !opName) return;
  const res = await api('POST', '/api/operators/claim', { operator: opName, target });
  if (res?.status === 'conflict') toast(`⚠ Conflict: ${res.warning}`);
  $('claim-input').value = '';
  loadOperators();
}

async function releaseTarget(target) {
  await fetch(`${SERVER}/api/operators/claim/${encodeURIComponent(target)}?operator=${encodeURIComponent(opName)}`, {
    method: 'DELETE',
  });
  loadOperators();
}

async function addTarget() {
  const cidr = $('target-input').value.trim();
  if (!cidr) return;
  await api('POST', '/api/targets', { cidr });
  $('target-input').value = '';
  loadTargets();
}

async function addLoot() {
  const text = $('loot-text').value.trim();
  const loot_type = $('loot-type').value;
  if (!text) return;
  await api('POST', '/api/loot', { loot_type, text, operator: opName || 'dashboard' });
  $('loot-text').value = '';
  loadLoot();
}

async function addNote() {
  const text = $('note-text').value.trim();
  if (!text) return;
  await api('POST', '/api/notes', { text, operator: opName || 'dashboard' });
  $('note-text').value = '';
  loadNotes();
}

async function killSession(id) {
  if (!confirm(`Kill session #${id}?`)) return;
  await fetch(`${SERVER}/api/sessions/${id}`, { method: 'DELETE' });
  loadSessions();
}

async function broadcast() {
  const msg = $('bcast-input').value.trim();
  if (!msg) return;
  await api('POST', '/api/events/broadcast', { message: msg, operator: opName || 'dashboard' });
  $('bcast-input').value = '';
}

// ── Enter-to-submit ───────────────────────────────────────────────────────────
['claim-input',  'claimTarget',
 'target-input', 'addTarget',
 'loot-text',    'addLoot',
 'note-text',    'addNote',
 'bcast-input',  'broadcast',
].reduce((_, __, i, a) => {
  if (i % 2 === 0) {
    const el = $(a[i]);
    if (el) el.addEventListener('keydown', e => { if (e.key === 'Enter') eval(a[i + 1] + '()'); });
  }
}, null);

// ── SSE feed ──────────────────────────────────────────────────────────────────
const EVT_COLOR = {
  session_opened: 'b-green', session_killed: 'b-red',
  loot_added: 'b-yellow', note_added: 'b-cyan',
  target_added: 'b-cyan', operator_joined: 'b-green',
  operator_left: 'b-grey', target_claimed: 'b-cyan',
  target_released: 'b-grey', target_conflict: 'b-yellow',
  operator_message: 'b-cyan',
};

function pushEvent(evt) {
  const feed = $('event-feed');
  const div = document.createElement('div');
  div.className = 'evt-row';
  const color = EVT_COLOR[evt.type] || 'b-grey';
  const detail = evt.data ? JSON.stringify(evt.data).replace(/[{}"]/g, '').slice(0, 70) : '';
  div.innerHTML = `
    <span class="evt-ts">${ts(evt.t || new Date().toISOString())}</span>
    <div class="evt-body">
      <span class="badge ${color}">${evt.type}</span>
      ${detail ? `<div class="evt-detail">${detail}</div>` : ''}
    </div>`;
  feed.prepend(div);
  while (feed.children.length > 120) feed.removeChild(feed.lastChild);
}

function clearFeed() { $('event-feed').innerHTML = ''; }

function connectSSE() {
  if (sse) sse.close();
  sse = new EventSource(SERVER + '/api/events');
  sse.onopen = () => {
    $('server-dot').className = 'dot dot-live';
    $('server-label').textContent = 'Live';
  };
  sse.onmessage = e => {
    let evt; try { evt = JSON.parse(e.data); } catch { return; }
    if (evt.type === 'ping' || evt.type === 'connected') return;
    pushEvent(evt);
    const refresh = {
      session_opened: loadSessions, session_killed: loadSessions,
      loot_added: loadLoot, note_added: loadNotes,
      target_added: loadTargets,
      operator_joined: loadOperators, operator_left: loadOperators,
      target_claimed: loadOperators, target_released: loadOperators,
      target_conflict: () => { loadOperators(); toast(`⚠ Conflict: ${(evt.data||{}).target||''}`); },
    };
    (refresh[evt.type] || (() => {}))();
  };
  sse.onerror = () => {
    $('server-dot').className = 'dot dot-err';
    $('server-label').textContent = 'Reconnecting…';
    sse.close();
    setTimeout(connectSSE, 4000);
  };
}

// ── Init ──────────────────────────────────────────────────────────────────────
boot();
setInterval(loadAll, 15000);
