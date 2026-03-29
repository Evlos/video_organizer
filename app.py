# app.py
import os
import json
import re
import subprocess
import configparser
from flask import Flask, render_template_string, send_from_directory, jsonify, request, abort

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')

app = Flask(__name__)

def get_video_duration(filepath):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
            capture_output=True, text=True, timeout=10
        )
        seconds = float(result.stdout.strip())
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    except:
        return "--:--"

def load_tags():
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cfg.read(CONFIG_FILE, encoding='utf-8')
    tags = []
    if cfg.has_option('tags', 'list'):
        raw = cfg.get('tags', 'list').strip()
        if raw:
            tags = [t for t in raw.split(',') if t]
    return tags

def save_tags(tags):
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        cfg.read(CONFIG_FILE, encoding='utf-8')
    if not cfg.has_section('tags'):
        cfg.add_section('tags')
    cfg.set('tags', 'list', ','.join(tags))
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        cfg.write(f)

def split_tags(prefix):
    # split by digit boundaries: 1b2k -> ['1b','2k']
    parts = re.findall(r'\d+[a-zA-Z]+|[a-zA-Z]+\d+|\d+|[a-zA-Z]+', prefix)
    # regroup: digit(s)+letter(s) or letter(s)+digit(s)
    tags = re.findall(r'(?:\d+[a-zA-Z_-]+|[a-zA-Z_-]+\d+)', prefix)
    if not tags:
        tags = parts
    return [t for t in tags if t]

HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>VIDEO ORGANIZER</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0a0a0a; --panel: #0f0f0f; --border: #1e1e1e;
    --green: #00ff41; --green-dim: #00aa28; --green-dark: #003310;
    --red: #ff3030; --red-dim: #881010;
    --text: #c8ffc8; --text-dim: #557755;
  }
  html, body { height: 100%; background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; overflow: hidden; }
  #app { display: flex; height: 100vh; }

  /* LEFT */
  #left { width: 33.333%; border-right: 1px solid var(--border); display: flex; flex-direction: column; background: var(--panel); }
  #left-header { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 11px; color: var(--green); letter-spacing: 2px; text-transform: uppercase; }
  #file-list { flex: 1; overflow-y: auto; }
  #file-list::-webkit-scrollbar { width: 4px; }
  #file-list::-webkit-scrollbar-thumb { background: var(--green-dim); }
  .file-item { display: flex; align-items: center; padding: 10px 16px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.15s; gap: 6px; }
  .file-item:hover { background: #111; }
  .file-item.active { background: var(--green-dark); border-left: 2px solid var(--green); }
  .file-item.pending-delete { opacity: 0.4; text-decoration: line-through; }
  .has-json-icon { font-size: 12px; flex-shrink: 0; color: var(--green); }
  .file-name { flex: 1; font-size: 12px; color: var(--text); word-break: break-all; }
  .file-dur { font-size: 11px; color: var(--text-dim); white-space: nowrap; }
  .trash-btn { background: none; border: none; cursor: pointer; color: var(--text-dim); font-size: 14px; padding: 2px 4px; flex-shrink: 0; }
  .trash-btn:hover { color: var(--red); }
  .trash-btn.marked { color: var(--red); }
  #left-footer { padding: 12px 16px; border-top: 1px solid var(--border); }
  #delete-all-btn { width: 100%; padding: 8px; background: transparent; border: 1px solid var(--red-dim); color: var(--red); font-family: 'Courier New', monospace; font-size: 12px; letter-spacing: 1px; cursor: pointer; text-transform: uppercase; }
  #delete-all-btn:hover { background: var(--red-dim); color: #fff; }
  #delete-all-btn:disabled { opacity: 0.3; cursor: not-allowed; }

  /* RIGHT */
  #right { flex: 1; display: flex; flex-direction: column; background: #000; min-width: 0; }
  #video-wrapper { flex: 1; display: flex; align-items: center; justify-content: center; background: #000; overflow: hidden; cursor: pointer; position: relative; }
  video { max-width: 100%; max-height: 100%; display: block; }
  #no-video { color: var(--text-dim); font-size: 13px; letter-spacing: 2px; pointer-events: none; }
  #play-overlay { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); font-size: 48px; opacity: 0; pointer-events: none; transition: opacity 0.3s; }
  #play-overlay.show { animation: fadeout 0.6s forwards; }
  @keyframes fadeout { 0%{opacity:1} 70%{opacity:1} 100%{opacity:0} }

  /* PROGRESS AREA */
  #progress-area { background: var(--panel); border-top: 1px solid var(--border); display: flex; flex-direction: column; padding: 10px 16px; gap: 8px; flex-shrink: 0; }
  #time-display { font-size: 10px; color: var(--text-dim); letter-spacing: 1px; }
  #progress-container { position: relative; width: 100%; height: 40px; cursor: pointer; display: flex; align-items: center; }
  #progress-track { position: absolute; left: 0; right: 0; height: 6px; background: #1c1c1c; border-radius: 3px; }
  #progress-bar { height: 100%; background: var(--green-dim); border-radius: 3px; width: 0%; pointer-events: none; }
  #progress-head { position: absolute; top: 50%; transform: translate(-50%,-50%); width: 12px; height: 12px; border-radius: 50%; background: var(--green); left: 0%; pointer-events: none; box-shadow: 0 0 6px var(--green); }
  #progress-container.dragging #progress-head { transform: translate(-50%,-50%) scale(1.4); }
  #markers-layer { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
  .segment-highlight { position: absolute; top: 50%; transform: translateY(-50%); height: 6px; background: rgba(0,255,65,0.25); border-top: 1px solid var(--green-dim); border-bottom: 1px solid var(--green-dim); pointer-events: none; }
  .marker-brace { position: absolute; top: 50%; transform: translate(-50%,-50%); font-size: 18px; color: var(--green); font-weight: bold; pointer-events: none; text-shadow: 0 0 6px var(--green); }

  /* CONTROLS ROW */
  #controls-row { display: flex; align-items: center; gap: 8px; }
  #controls-left { display: flex; gap: 8px; }
  #controls-center { flex: 1; display: flex; justify-content: center; }
  #controls-right { display: flex; gap: 8px; }
  .ctrl-btn { padding: 7px 14px; background: transparent; border: 1px solid var(--green-dim); color: var(--green); font-family: 'Courier New', monospace; font-size: 11px; cursor: pointer; letter-spacing: 1px; text-transform: uppercase; transition: all 0.15s; white-space: nowrap; flex-shrink: 0; border-radius: 2px; touch-action: manipulation; }
  .ctrl-btn:hover { background: var(--green-dark); box-shadow: 0 0 8px var(--green-dim); }
  .ctrl-btn:active { background: var(--green-dim); color: #000; }
  .ctrl-btn.danger { border-color: #664400; color: #cc8800; }
  .ctrl-btn.danger:hover { background: #331f00; }

  /* MODAL */
  #modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 1000; align-items: center; justify-content: center; }
  #modal-overlay.open { display: flex; }
  #modal { background: var(--panel); border: 1px solid var(--green-dim); padding: 24px; width: 480px; max-width: 90vw; box-shadow: 0 0 30px rgba(0,255,65,0.15); }
  #modal h3 { color: var(--green); font-size: 13px; letter-spacing: 2px; margin-bottom: 16px; text-transform: uppercase; }
  #modal-input { width: 100%; background: #000; border: 1px solid var(--green-dim); color: var(--green); font-family: 'Courier New', monospace; font-size: 14px; padding: 10px 12px; outline: none; letter-spacing: 1px; }
  #modal-input:focus { border-color: var(--green); box-shadow: 0 0 8px rgba(0,255,65,0.3); }
  #modal-preview { font-size: 11px; color: var(--text-dim); margin: 8px 0 4px 0; min-height: 16px; }
  #tag-list { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 16px 0; min-height: 28px; }
  .tag-chip { padding: 4px 10px; border: 1px solid var(--green-dim); color: var(--green-dim); font-size: 11px; cursor: pointer; border-radius: 2px; font-family: 'Courier New', monospace; transition: all 0.15s; }
  .tag-chip:hover { background: var(--green-dark); color: var(--green); border-color: var(--green); }
  #modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
  #modal-confirm-btn { padding: 8px 20px; background: var(--green-dark); border: 1px solid var(--green-dim); color: var(--green); font-family: 'Courier New', monospace; font-size: 12px; cursor: pointer; letter-spacing: 1px; text-transform: uppercase; }
  #modal-confirm-btn:hover { background: var(--green-dim); color: #000; }
  #modal-cancel-btn { padding: 8px 20px; background: transparent; border: 1px solid #333; color: var(--text-dim); font-family: 'Courier New', monospace; font-size: 12px; cursor: pointer; letter-spacing: 1px; text-transform: uppercase; }
  #modal-cancel-btn:hover { border-color: #555; color: var(--text); }

  body::after { content: ''; position: fixed; inset: 0; background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px); pointer-events: none; z-index: 9999; }
</style>
</head>
<body>
<div id="app">
  <div id="left">
    <div id="left-header">▍ VIDEO ORGANIZER</div>
    <div id="file-list"></div>
    <div id="left-footer">
      <button id="delete-all-btn" disabled onclick="confirmDeleteAll()">⚠ PURGE</button>
    </div>
  </div>

  <div id="right">
    <div id="video-wrapper" onclick="togglePlay()">
      <div id="no-video">// SELECT FILE TO PLAY</div>
      <video id="player" style="display:none" preload="metadata"></video>
      <div id="play-overlay"></div>
    </div>

    <div id="progress-area">
      <div id="time-display">00:00 / 00:00</div>
      <div id="progress-container">
        <div id="progress-track">
          <div id="progress-bar"></div>
          <div id="progress-head"></div>
        </div>
        <div id="markers-layer"></div>
      </div>
      <div id="controls-row">
        <div id="controls-left">
          <button class="ctrl-btn danger" onclick="clearMarkers()">✕ CLEAR</button>
          <button class="ctrl-btn danger" onclick="undoMarker()">↩ UNDO</button>
        </div>
        <div id="controls-center">
          <button class="ctrl-btn" onclick="openRenameModal()">✎ RENAME</button>
        </div>
        <div id="controls-right">
          <button class="ctrl-btn" onclick="markSegment('start')">{ Mark In</button>
          <button class="ctrl-btn" onclick="markSegment('end')">Mark Out }</button>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Rename Modal -->
<div id="modal-overlay">
  <div id="modal">
    <h3>✎ RENAME VIDEO</h3>
    <input id="modal-input" type="text" placeholder="Please enter a prefix, e.g. 1b2k" autocomplete="off" spellcheck="false" />
    <div id="modal-preview"></div>
    <div id="tag-list"></div>
    <div id="modal-actions">
      <button id="modal-cancel-btn" onclick="closeModal()">CANCEL</button>
      <button id="modal-confirm-btn" onclick="doRename()">RENAME</button>
    </div>
  </div>
</div>

<script>
const player = document.getElementById('player');
const progressBar = document.getElementById('progress-bar');
const progressHead = document.getElementById('progress-head');
const progressContainer = document.getElementById('progress-container');
const markersLayer = document.getElementById('markers-layer');
const timeDisplay = document.getElementById('time-display');
const fileListEl = document.getElementById('file-list');
const deleteAllBtn = document.getElementById('delete-all-btn');
const playOverlay = document.getElementById('play-overlay');
const modalOverlay = document.getElementById('modal-overlay');
const modalInput = document.getElementById('modal-input');
const modalPreview = document.getElementById('modal-preview');
const tagListEl = document.getElementById('tag-list');

let markers = [];
let pendingDeletes = new Set();
let isDragging = false;
let currentFile = null;
let knownTags = [];

// ── Helpers ──────────────────────────────────────────────
function fmtTime(s) {
  s = Math.floor(s);
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
  if (h > 0) return `${pad(h)}:${pad(m)}:${pad(sec)}`;
  return `${pad(m)}:${pad(sec)}`;
}
function pad(n) { return String(n).padStart(2,'0'); }

function splitTags(prefix) {
  // split on digit/letter boundaries: 1b2k -> ['1b','2k']
  return (prefix.match(/(?:\d+[a-zA-Z_-]+|[a-zA-Z_-]+\d+)/g) || []);
}

// ── Progress / Playback ───────────────────────────────────
function updateProgress() {
  if (!player.duration) return;
  const pct = (player.currentTime / player.duration) * 100;
  progressBar.style.width = pct + '%';
  progressHead.style.left = pct + '%';
  timeDisplay.textContent = fmtTime(player.currentTime) + ' / ' + fmtTime(player.duration);
}
player.addEventListener('timeupdate', updateProgress);
player.addEventListener('loadedmetadata', () => { updateProgress(); renderMarkers(); });

function togglePlay() {
  if (!player.src || !player.duration) return;
  if (player.paused) { player.play(); playOverlay.textContent = '▶'; }
  else { player.pause(); playOverlay.textContent = '⏸'; }
  playOverlay.classList.remove('show');
  void playOverlay.offsetWidth;
  playOverlay.classList.add('show');
}

function getPercent(clientX) {
  const rect = progressContainer.getBoundingClientRect();
  return Math.max(0, Math.min(100, (clientX - rect.left) / rect.width * 100));
}
function seekTo(pct) {
  if (!player.duration) return;
  player.currentTime = pct / 100 * player.duration;
  updateProgress();
}

progressContainer.addEventListener('mousedown', e => {
  isDragging = true; progressContainer.classList.add('dragging');
  seekTo(getPercent(e.clientX)); e.preventDefault();
});
document.addEventListener('mousemove', e => { if (isDragging) seekTo(getPercent(e.clientX)); });
document.addEventListener('mouseup', () => { isDragging = false; progressContainer.classList.remove('dragging'); });

progressContainer.addEventListener('touchstart', e => {
  isDragging = true; seekTo(getPercent(e.touches[0].clientX)); e.preventDefault();
}, { passive: false });
progressContainer.addEventListener('touchmove', e => {
  if (isDragging) seekTo(getPercent(e.touches[0].clientX)); e.preventDefault();
}, { passive: false });
progressContainer.addEventListener('touchend', () => { isDragging = false; });

// ── Markers ───────────────────────────────────────────────
function markSegment(type) {
  if (!player.src || !player.duration) return;
  markers.push({ type, time: player.currentTime });
  renderMarkers();
  saveMarkers();
}

function undoMarker() {
  if (!markers.length) return;
  markers.pop();
  renderMarkers();
  saveMarkers();
}

function clearMarkers() {
  if (!markers.length) return;
  if (!confirm('Clear all markers?')) return;
  markers = [];
  renderMarkers();
  saveMarkers();
}

function renderMarkers() {
  markersLayer.innerHTML = '';
  if (!player.duration) return;
  const dur = player.duration;
  const starts = markers.filter(m => m.type==='start').map(m=>m.time).sort((a,b)=>a-b);
  const ends   = markers.filter(m => m.type==='end').map(m=>m.time).sort((a,b)=>a-b);
  const pairs = [];
  let si=0, ei=0;
  while (si<starts.length && ei<ends.length) {
    if (ends[ei]>starts[si]) { pairs.push([starts[si],ends[ei]]); si++; ei++; }
    else ei++;
  }
  pairs.forEach(([s,e]) => {
    const el = document.createElement('div');
    el.className = 'segment-highlight';
    el.style.left  = (s/dur*100)+'%';
    el.style.width = ((e-s)/dur*100)+'%';
    markersLayer.appendChild(el);
  });
  markers.forEach(m => {
    const el = document.createElement('div');
    el.className = 'marker-brace';
    el.style.left = (m.time/dur*100)+'%';
    el.textContent = m.type==='start' ? '{' : '}';
    markersLayer.appendChild(el);
  });
}

function saveMarkers() {
  if (!currentFile || !player.duration) return;
  const dur = player.duration;
  // fill lonely markers
  const starts = markers.filter(m=>m.type==='start').map(m=>m.time).sort((a,b)=>a-b);
  const ends   = markers.filter(m=>m.type==='end').map(m=>m.time).sort((a,b)=>a-b);
  const pairs = [];
  let si=0, ei=0;
  while (si<starts.length && ei<ends.length) {
    if (ends[ei]>starts[si]) { pairs.push([starts[si],ends[ei]]); si++; ei++; }
    else ei++;
  }
  // leftover starts -> pair with video end
  while (si<starts.length) { pairs.push([starts[si], dur]); si++; }
  // leftover ends -> pair with video start (0)
  // collect all ends that were never paired
  // rebuild: any end < first paired start gets paired with 0
  const usedEnds = new Set(pairs.map(p=>p[1]).filter(v=>v!==dur));
  ends.forEach(e => {
    if (!usedEnds.has(e) && e!==dur) { pairs.push([0, e]); usedEnds.add(e); }
  });
  pairs.sort((a,b)=>a[0]-b[0]);
  const payload = { file: currentFile, duration: dur, markers: markers, segments: pairs.map(([s,e])=>({start:s,end:e})) };
  fetch('/save_markers', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  }).then(r=>r.json()).then(d=>{ if(d.ok) loadFileList(); });
}

function loadMarkersFromFile(filename) {
  fetch('/load_markers/' + encodeURIComponent(filename))
    .then(r=>r.json())
    .then(d=>{ markers = d.markers || []; renderMarkers(); });
}

// ── File list ─────────────────────────────────────────────
function loadFile(filename) {
  currentFile = filename;
  markers = [];
  markersLayer.innerHTML = '';
  progressBar.style.width = '0%';
  progressHead.style.left = '0%';
  document.getElementById('no-video').style.display = 'none';
  player.style.display = 'block';
  player.src = '/video/' + encodeURIComponent(filename);
  player.play();
  document.querySelectorAll('.file-item').forEach(el => el.classList.toggle('active', el.dataset.name===filename));
  loadMarkersFromFile(filename);
}

function toggleDelete(filename, btn) {
  if (pendingDeletes.has(filename)) {
    pendingDeletes.delete(filename);
    btn.classList.remove('marked');
    btn.closest('.file-item').classList.remove('pending-delete');
  } else {
    pendingDeletes.add(filename);
    btn.classList.add('marked');
    btn.closest('.file-item').classList.add('pending-delete');
  }
  deleteAllBtn.disabled = pendingDeletes.size === 0;
}

function confirmDeleteAll() {
  if (!pendingDeletes.size) return;
  if (!confirm(`Delete ${pendingDeletes.size} file(s)\n\n${Array.from(pendingDeletes).join('\n')}`)) return;
  fetch('/delete', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({files: Array.from(pendingDeletes)})
  }).then(r=>r.json()).then(d=>{ if(d.ok){ pendingDeletes.clear(); loadFileList(); } else alert('Delete failed: '+d.error); });
}

function loadFileList() {
  fetch('/files').then(r=>r.json()).then(files=>{
    fileListEl.innerHTML = '';
    files.forEach(f=>{
      const item = document.createElement('div');
      item.className = 'file-item';
      item.dataset.name = f.name;
      if (f.name===currentFile) item.classList.add('active');
      const safe = f.name.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
      item.innerHTML = `
        ${f.has_json ? '<span class="has-json-icon" title="Has markers">◈</span>' : '<span style="width:16px;display:inline-block"></span>'}
        <span class="file-name">${f.name}</span>
        <span class="file-dur">${f.duration}</span>
        <button class="trash-btn" title="Mark for deletion" onclick="event.stopPropagation();toggleDelete('${safe}',this)">🗑</button>
      `;
      item.addEventListener('click', ()=>loadFile(f.name));
      fileListEl.appendChild(item);
    });
  });
}

// ── Rename Modal ──────────────────────────────────────────
function openRenameModal() {
  if (!currentFile) { alert('Please select a video file first'); return; }
  modalInput.value = '';
  modalPreview.textContent = '';
  renderTagChips();
  modalOverlay.classList.add('open');
  modalInput.focus();
}

function closeModal() { modalOverlay.classList.remove('open'); }

modalInput.addEventListener('input', () => {
  const val = modalInput.value.trim();
  if (val) {
    modalPreview.textContent = '→ ' + val + currentFile;
    const tags = splitTags(val);
    // show inline detected tags
  } else {
    modalPreview.textContent = '';
  }
});

modalInput.addEventListener('keydown', e => { if (e.key==='Enter') doRename(); if (e.key==='Escape') closeModal(); });

function renderTagChips() {
  tagListEl.innerHTML = '';
  knownTags.forEach(tag => {
    const chip = document.createElement('span');
    chip.className = 'tag-chip';
    chip.textContent = tag;
    chip.onclick = () => { modalInput.value += tag; modalInput.dispatchEvent(new Event('input')); modalInput.focus(); };
    tagListEl.appendChild(chip);
  });
}

function doRename() {
  const prefix = modalInput.value.trim();
  if (!prefix) { alert('Please enter a prefix'); return; }
  if (!currentFile) return;
  const newName = prefix + currentFile;
  fetch('/rename', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ old_name: currentFile, new_name: newName, prefix: prefix })
  }).then(r=>r.json()).then(d=>{
    if (d.ok) {
      knownTags = d.tags;
      renderTagChips();
      closeModal();
      currentFile = newName;
      loadFileList();
      // reload video with new name
      const wasPlaying = !player.paused;
      const ct = player.currentTime;
      player.src = '/video/' + encodeURIComponent(newName);
      player.currentTime = ct;
      if (wasPlaying) player.play();
    } else {
      alert('Rename failed: ' + (d.error||''));
    }
  });
}

// ── Init ──────────────────────────────────────────────────
fetch('/tags').then(r=>r.json()).then(d=>{ knownTags=d.tags; });
loadFileList();

// close modal on overlay click
modalOverlay.addEventListener('click', e=>{ if(e.target===modalOverlay) closeModal(); });
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/files')
def list_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    files = []
    for f in os.listdir(DATA_DIR):
        if f.lower().endswith('.mp4'):
            fp = os.path.join(DATA_DIR, f)
            jp = os.path.join(DATA_DIR, os.path.splitext(f)[0] + '.json')
            mtime = os.path.getmtime(fp)
            dur = get_video_duration(fp)
            files.append({'name': f, 'mtime': mtime, 'duration': dur, 'has_json': os.path.exists(jp)})
    files.sort(key=lambda x: x['mtime'], reverse=True)
    return jsonify(files)

@app.route('/video/<filename>')
def serve_video(filename):
    safe = os.path.basename(filename)
    fp = os.path.join(DATA_DIR, safe)
    if not os.path.exists(fp):
        abort(404)
    return send_from_directory(DATA_DIR, safe, conditional=True)

@app.route('/save_markers', methods=['POST'])
def save_markers():
    data = request.get_json()
    filename = os.path.basename(data.get('file', ''))
    if not filename:
        return jsonify({'ok': False, 'error': 'no file'})
    json_path = os.path.join(DATA_DIR, os.path.splitext(filename)[0] + '.json')
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/load_markers/<filename>')
def load_markers(filename):
    safe = os.path.basename(filename)
    json_path = os.path.join(DATA_DIR, os.path.splitext(safe)[0] + '.json')
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({'markers': [], 'segments': []})

@app.route('/delete', methods=['POST'])
def delete_files():
    data = request.get_json()
    errors = []
    for name in data.get('files', []):
        safe = os.path.basename(name)
        for ext in [safe, os.path.splitext(safe)[0] + '.json']:
            fp = os.path.join(DATA_DIR, ext)
            try:
                if os.path.exists(fp):
                    os.remove(fp)
            except Exception as e:
                errors.append(str(e))
    if errors:
        return jsonify({'ok': False, 'error': '; '.join(errors)})
    return jsonify({'ok': True})

@app.route('/rename', methods=['POST'])
def rename_file():
    data = request.get_json()
    old_name = os.path.basename(data.get('old_name', ''))
    new_name = os.path.basename(data.get('new_name', ''))
    prefix   = data.get('prefix', '')
    if not old_name or not new_name:
        return jsonify({'ok': False, 'error': 'invalid names'})
    old_mp4  = os.path.join(DATA_DIR, old_name)
    new_mp4  = os.path.join(DATA_DIR, new_name)
    old_json = os.path.join(DATA_DIR, os.path.splitext(old_name)[0] + '.json')
    new_json = os.path.join(DATA_DIR, os.path.splitext(new_name)[0] + '.json')
    if not os.path.exists(old_mp4):
        return jsonify({'ok': False, 'error': 'source not found'})
    if os.path.exists(new_mp4):
        return jsonify({'ok': False, 'error': 'target file already exists'})
    try:
        os.rename(old_mp4, new_mp4)
        if os.path.exists(old_json):
            os.rename(old_json, new_json)
            # update file field inside json
            with open(new_json, 'r', encoding='utf-8') as f:
                jdata = json.load(f)
            jdata['file'] = new_name
            with open(new_json, 'w', encoding='utf-8') as f:
                json.dump(jdata, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

    # handle tags
    new_tags = split_tags(prefix)
    existing = load_tags()
    merged = existing[:]
    for t in new_tags:
        if t not in merged:
            merged.append(t)
    save_tags(merged)
    return jsonify({'ok': True, 'tags': merged})

@app.route('/tags')
def get_tags():
    return jsonify({'tags': load_tags()})

if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
