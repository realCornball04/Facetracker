HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FaceTrack v22</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: #0a0a0a;
    color: #e0e0e0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    display: flex;
    height: 100vh;
    width: 100vw;
    overflow: hidden;
  }

  /* ── Sidebar ── */
  #sidebar {
    width: 220px;
    min-width: 220px;
    background: #111;
    border-right: 1px solid #222;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: width 0.25s ease, min-width 0.25s ease, padding 0.25s ease;
    padding: 10px;
    gap: 0;
  }

  #sidebar.collapsed {
    width: 0;
    min-width: 0;
    padding: 0;
  }

  /* Sidebar inner — scrollbar versteckt, aber scrollbar */
  #sidebar-inner {
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
    overflow-x: hidden;
    flex: 1;
    /* Scrollbar unsichtbar machen */
    scrollbar-width: none;
  }
  #sidebar-inner::-webkit-scrollbar { display: none; }

  #sidebar h1 {
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    letter-spacing: 1px;
    padding-bottom: 8px;
    border-bottom: 1px solid #222;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .section-title {
    font-size: 10px;
    font-weight: 600;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 4px;
    white-space: nowrap;
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex-shrink: 0;
  }

  /* Status */
  #conn-status {
    padding: 5px 10px;
    border-radius: 6px;
    text-align: center;
    font-weight: 600;
    font-size: 12px;
    background: #1a1a1a;
    color: #f59e0b;
    transition: background 0.3s, color 0.3s;
    white-space: nowrap;
  }
  #conn-status.ok  { background: #052e16; color: #4ade80; }
  #conn-status.err { background: #2d0a0a; color: #f87171; }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 3px 8px;
    background: #1a1a1a;
    border-radius: 5px;
  }
  .stat-label { color: #777; font-size: 11px; }
  .stat-value { color: #fff; font-weight: 600; font-size: 11px; }

  /* Buttons */
  button {
    background: #1e1e1e;
    color: #bbb;
    border: 1px solid #2e2e2e;
    border-radius: 6px;
    padding: 6px 9px;
    cursor: pointer;
    font-size: 11px;
    transition: background 0.15s, border-color 0.15s, color 0.15s;
    width: 100%;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  button:hover { background: #2a2a2a; border-color: #555; color: #fff; }
  button.active { background: #1d3a1d; border-color: #4ade80; color: #4ade80; }
  button.active-red { background: #3a1d1d; border-color: #f87171; color: #f87171; }
  button.active-rainbow {
    background: linear-gradient(90deg,#ff000022,#ff7f0022,#ffff0022,#00ff0022,#0000ff22,#8b00ff22);
    border-color: #a78bfa; color: #a78bfa;
  }

  .btn-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
  }

  /* Color Picker */
  .color-row {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #1a1a1a;
    border-radius: 6px;
    padding: 5px 8px;
  }
  .color-row label { color: #888; font-size: 11px; flex: 1; }
  input[type="color"] {
    width: 30px; height: 22px;
    border: none; border-radius: 4px;
    cursor: pointer; background: none; padding: 0;
  }

  /* Face List */
  #face-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
    max-height: 80px;
    overflow-y: auto;
    scrollbar-width: none;
  }
  #face-list::-webkit-scrollbar { display: none; }
  .face-item {
    font-size: 10px; color: #aaa;
    background: #1a1a1a; border-radius: 4px;
    padding: 2px 6px; font-family: monospace;
    white-space: nowrap;
  }
  #no-faces { color: #444; font-size: 11px; font-style: italic; }

  #konami-hint {
    font-size: 9px; color: #2a2a2a;
    text-align: center;
    padding-top: 6px;
    white-space: nowrap;
    transition: color 0.3s;
    flex-shrink: 0;
  }

  /* ── Toggle Button ── */
  #toggle-btn {
    position: fixed;
    top: 50%;
    transform: translateY(-50%);
    left: 220px;
    z-index: 100;
    width: 18px;
    height: 48px;
    background: #1e1e1e;
    border: 1px solid #333;
    border-left: none;
    border-radius: 0 6px 6px 0;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    font-size: 10px;
    transition: left 0.25s ease, color 0.15s;
    padding: 0;
  }
  #toggle-btn:hover { color: #fff; background: #2a2a2a; }
  #toggle-btn.collapsed { left: 0; border-left: 1px solid #333; border-radius: 0 6px 6px 0; }

  /* ── Main Video ── */
  #main {
    flex: 1;
    display: flex;
    align-items: stretch;
    justify-content: center;
    background: #050505;
    position: relative;
    overflow: hidden;
    min-width: 0;
  }

  #stream {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }

  #overlay-msg {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(0,0,0,0.75);
    color: #4ade80;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 20px;
    font-weight: 700;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.4s;
    white-space: nowrap;
  }
  #overlay-msg.show { opacity: 1; }

  #rec-indicator {
    position: absolute;
    top: 12px; right: 12px;
    display: none;
    align-items: center;
    gap: 6px;
    background: rgba(0,0,0,0.65);
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    color: #f87171;
  }
  #rec-indicator.show { display: flex; }
  .rec-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #f87171;
    animation: blink 1s infinite;
  }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.2} }

  #matrix-overlay {
    position: absolute;
    inset: 0;
    pointer-events: none;
    display: none;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    color: #00ff44;
    text-shadow: 0 0 12px #00ff44;
    font-weight: 900;
    letter-spacing: 4px;
    animation: mpulse 2s infinite;
  }
  #matrix-overlay.show { display: flex; }
  @keyframes mpulse { 0%,100%{opacity:0.5} 50%{opacity:1} }
</style>
</head>
<body>

<!-- ── Sidebar ─────────────────────────────────────────────── -->
<div id="sidebar">
  <div id="sidebar-inner">
    <h1>⬡ FaceTrack <span style="color:#4ade80;font-size:10px;">v22</span></h1>

    <!-- Status -->
    <div class="section">
      <div class="section-title">Status</div>
      <div id="conn-status">Verbinde...</div>
      <div class="stat-row">
        <span class="stat-label">FPS</span>
        <span class="stat-value" id="val-fps">—</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Gesichter</span>
        <span class="stat-value" id="val-faces">—</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Uptime</span>
        <span class="stat-value" id="val-uptime">—</span>
      </div>
    </div>

    <!-- Box Style -->
    <div class="section">
      <div class="section-title">Box Style</div>
      <div class="btn-grid">
        <button onclick="setStyle('corners')"   id="s-corners">⌐ Corners</button>
        <button onclick="setStyle('rect')"      id="s-rect">▭ Rect</button>
        <button onclick="setStyle('circle')"    id="s-circle">◯ Circle</button>
        <button onclick="setStyle('crosshair')" id="s-crosshair">✛ Cross</button>
        <button onclick="setStyle('sniper')"    id="s-sniper">🎯 Sniper</button>
        <button onclick="setStyle('dot')"       id="s-dot">• Dot</button>
        <button onclick="setStyle('hitmarker')" id="s-hitmarker">✕ Hit</button>
        <button onclick="setStyle('none')"      id="s-none">✗ None</button>
      </div>
    </div>

    <!-- Farbe -->
    <div class="section">
      <div class="section-title">Box Farbe</div>
      <div class="color-row">
        <label>Farbe wählen</label>
        <input type="color" id="color-picker" value="#ffffff"
               oninput="setColor(this.value)">
      </div>
    </div>

    <!-- Filter -->
    <div class="section">
      <div class="section-title">😎 Face Filter</div>
      <div class="btn-grid">
        <button onclick="setFilter('none')"       id="f-none">✗ Off</button>
        <button onclick="setFilter('sunglasses')" id="f-sunglasses">🕶️ Brille</button>
        <button onclick="setFilter('hat')"        id="f-hat">🎩 Hut</button>
        <button onclick="setFilter('clown')"      id="f-clown">🤡 Clown</button>
        <button onclick="setFilter('pixel')"      id="f-pixel">🔲 Pixel</button>
        <button onclick="setFilter('matrix')"     id="f-matrix-filter">☠️ Matrix</button>
      </div>
    </div>

    <!-- Sondermodi -->
    <div class="section">
      <div class="section-title">✨ Sondermodi</div>
      <button onclick="toggleDisco()"  id="btn-disco">🌈 Disco-Modus</button>
      <button onclick="toggleMatrix()" id="btn-matrix">☠️ Matrix-Modus</button>
    </div>

    <!-- Recording -->
    <div class="section">
      <div class="section-title">🎬 Recording</div>
      <button onclick="toggleRecording()" id="btn-rec">⏺ Aufnahme starten</button>
      <div class="stat-row" id="rec-timer-row" style="display:none">
        <span class="stat-label">Dauer</span>
        <span class="stat-value" id="rec-timer">00:00</span>
      </div>
    </div>

    <!-- Snapshot -->
    <div class="section">
      <div class="section-title">📸 Snapshot</div>
      <button onclick="takeSnapshot()">📸 Snapshot speichern</button>
    </div>

    <!-- Face IDs -->
    <div class="section">
      <div class="section-title">👁 Gesichter</div>
      <div id="face-list">
        <div id="no-faces">Keine Gesichter</div>
      </div>
    </div>

    <div id="konami-hint">↑↑↓↓←→←→BA = 🟢</div>
  </div>
</div>

<!-- ── Sidebar Toggle Button ───────────────────────────────── -->
<button id="toggle-btn" onclick="toggleSidebar()" title="Sidebar ein/ausklappen">‹</button>

<!-- ── Video ───────────────────────────────────────────────── -->
<div id="main">
  <img id="stream" src="/video_feed" alt="Stream">
  <div id="overlay-msg"></div>
  <div id="rec-indicator"><div class="rec-dot"></div> REC</div>
  <div id="matrix-overlay">[ MATRIX MODE ]</div>
</div>

<script>
// ── State ─────────────────────────────────────────────────────────────────
let discoOn     = false;
let matrixOn    = false;
let recordingOn = false;
let recStart    = null;
let recInterval = null;
let sidebarOpen = true;

// ── Sidebar Toggle ────────────────────────────────────────────────────────
function toggleSidebar() {
  sidebarOpen = !sidebarOpen;
  const sb  = document.getElementById('sidebar');
  const btn = document.getElementById('toggle-btn');
  if (sidebarOpen) {
    sb.classList.remove('collapsed');
    btn.classList.remove('collapsed');
    btn.textContent = '‹';
    btn.style.left  = '220px';
  } else {
    sb.classList.add('collapsed');
    btn.classList.add('collapsed');
    btn.textContent = '›';
    btn.style.left  = '0px';
  }
}

// ── API Helper ────────────────────────────────────────────────────────────
function post(url, data) {
  return fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  });
}

// ── Box Style ─────────────────────────────────────────────────────────────
function setStyle(s) {
  post('/set_style', {style: s});
  document.querySelectorAll('[id^="s-"]').forEach(b => b.classList.remove('active'));
  const el = document.getElementById('s-' + s);
  if (el) el.classList.add('active');
}

// ── Box Farbe ─────────────────────────────────────────────────────────────
function setColor(hex) {
  post('/set_color', {color: hex});
}

// ── Face Filter ───────────────────────────────────────────────────────────
function setFilter(f) {
  post('/set_filter', {filter: f});
  document.querySelectorAll('[id^="f-"]').forEach(b => b.classList.remove('active'));
  const el = document.getElementById('f-' + f);
  if (el) el.classList.add('active');
}

// ── Disco ─────────────────────────────────────────────────────────────────
function toggleDisco() {
  discoOn = !discoOn;
  post('/set_disco', {enabled: discoOn});
  const btn = document.getElementById('btn-disco');
  btn.classList.toggle('active-rainbow', discoOn);
  btn.textContent = discoOn ? '🌈 Disco: ON' : '🌈 Disco-Modus';
}

// ── Matrix ────────────────────────────────────────────────────────────────
function setMatrix(state) {
  matrixOn = state;
  post('/set_matrix', {enabled: state});
  const btn = document.getElementById('btn-matrix');
  btn.classList.toggle('active', state);
  btn.textContent = state ? '☠️ Matrix: ON' : '☠️ Matrix-Modus';
  document.getElementById('matrix-overlay').classList.toggle('show', state);
}
function toggleMatrix() { setMatrix(!matrixOn); }

// ── Recording ─────────────────────────────────────────────────────────────
function toggleRecording() {
  if (!recordingOn) {
    post('/recording/start', {path: 'recording.avi'});
    recordingOn = true;
    recStart    = Date.now();
    document.getElementById('btn-rec').textContent = '⏹ Aufnahme stoppen';
    document.getElementById('btn-rec').classList.add('active-red');
    document.getElementById('rec-indicator').classList.add('show');
    document.getElementById('rec-timer-row').style.display = 'flex';
    recInterval = setInterval(updateRecTimer, 1000);
  } else {
    post('/recording/stop', {});
    recordingOn = false;
    clearInterval(recInterval);
    document.getElementById('btn-rec').textContent = '⏺ Aufnahme starten';
    document.getElementById('btn-rec').classList.remove('active-red');
    document.getElementById('rec-indicator').classList.remove('show');
    document.getElementById('rec-timer-row').style.display = 'none';
    document.getElementById('rec-timer').textContent = '00:00';
    showOverlay('✅ Aufnahme gespeichert');
  }
}

function updateRecTimer() {
  const s   = Math.floor((Date.now() - recStart) / 1000);
  const m   = String(Math.floor(s / 60)).padStart(2, '0');
  const sec = String(s % 60).padStart(2, '0');
  document.getElementById('rec-timer').textContent = m + ':' + sec;
}

// ── Snapshot ──────────────────────────────────────────────────────────────
function takeSnapshot() { window.open('/snapshot', '_blank'); }

// ── Overlay ───────────────────────────────────────────────────────────────
function showOverlay(msg, duration) {
  duration  = duration || 2500;
  const el  = document.getElementById('overlay-msg');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), duration);
}

// ── Uptime Format ─────────────────────────────────────────────────────────
function formatUptime(s) {
  if (s < 60) return s + 's';
  const m = Math.floor(s / 60);
  if (m < 60) return m + 'm ' + (s % 60) + 's';
  return Math.floor(m/60) + 'h ' + (m%60) + 'm';
}

// ── SSE ───────────────────────────────────────────────────────────────────
const evtSource = new EventSource('/events');

evtSource.onopen = function() {
  const cs = document.getElementById('conn-status');
  cs.textContent = '● Verbunden';
  cs.className   = 'ok';
};

evtSource.onerror = function() {
  const cs = document.getElementById('conn-status');
  cs.textContent = '● Verbindungsfehler';
  cs.className   = 'err';
};

evtSource.onmessage = function(e) {
  let d;
  try { d = JSON.parse(e.data); } catch { return; }

  document.getElementById('conn-status').textContent = '● Live';
  document.getElementById('conn-status').className   = 'ok';
  document.getElementById('val-fps').textContent     = (d.fps || 0) + ' fps';
  document.getElementById('val-faces').textContent   = d.faces || 0;
  document.getElementById('val-uptime').textContent  = formatUptime(d.uptime_s || 0);

  // Face-ID Liste
  const faceList = document.getElementById('face-list');
  const noFaces  = document.getElementById('no-faces');
  faceList.querySelectorAll('.face-item').forEach(el => el.remove());
  if (d.faces_coords && d.faces_coords.length > 0) {
    noFaces.style.display = 'none';
    d.faces_coords.forEach(function(f) {
      const div = document.createElement('div');
      div.className   = 'face-item';
      div.textContent = '#' + f.id + '  ' + f.box[2] + '×' + f.box[3];
      faceList.appendChild(div);
    });
  } else {
    noFaces.style.display = 'block';
  }
};

// ── Konami + Tastaturkürzel ───────────────────────────────────────────────
const KONAMI  = [38,38,40,40,37,39,37,39,66,65];
let konamiIdx = 0;

document.addEventListener('keydown', function(e) {
  // Konami
  if (e.keyCode === KONAMI[konamiIdx]) {
    konamiIdx++;
    if (konamiIdx === KONAMI.length) {
      konamiIdx = 0;
      setMatrix(true);
      showOverlay('🟢 MATRIX ACTIVATED', 3000);
      const hint = document.getElementById('konami-hint');
      hint.style.color = '#4ade80';
      setTimeout(() => hint.style.color = '#2a2a2a', 3000);
    }
  } else { konamiIdx = 0; }

  if (e.target.tagName === 'INPUT') return;
  if (e.key === 'd' || e.key === 'D') toggleDisco();
  if (e.key === 'm' || e.key === 'M') toggleMatrix();
  if (e.key === 'Escape') {
    if (matrixOn) setMatrix(false);
    if (discoOn)  toggleDisco();
    showOverlay('✖ Reset');
  }
});

// Init
setStyle('corners');
</script>
</body>
</html>
"""
