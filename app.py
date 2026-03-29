# app.py
import os
import json
import subprocess
from flask import Flask, render_template_string, send_from_directory, jsonify, request, abort

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

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

HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>VIDEO TERMINAL</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0a0a0a;
    --panel: #0f0f0f;
    --border: #1e1e1e;
    --green: #00ff41;
    --green-dim: #00aa28;
    --green-dark: #003310;
    --red: #ff3030;
    --red-dim: #881010;
    --text: #c8ffc8;
    --text-dim: #557755;
    --accent: #00ff41;
  }
  html, body { height: 100%; background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; overflow: hidden; }
  #app { display: flex; height: 100vh; }

  /* LEFT PANEL */
  #left { width: 33.333%; border-right: 1px solid var(--border); display: flex; flex-direction: column; background: var(--panel); }
  #left-header { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 11px; color: var(--green); letter-spacing: 2px; text-transform: uppercase; }
  #file-list { flex: 1; overflow-y: auto; }
  #file-list::-webkit-scrollbar { width: 4px; }
  #file-list::-webkit-scrollbar-track { background: var(--bg); }
  #file-list::-webkit-scrollbar-thumb { background: var(--green-dim); }
  .file-item { display: flex; align-items: center; padding: 10px 16px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.15s; gap: 8px; }
  .file-item:hover { background: #111; }
  .file-item.active { background: var(--green-dark); border-left: 2px solid var(--green); }
  .file-item.pending-delete { opacity: 0.4; text-decoration: line-through; }
  .file-name { flex: 1; font-size: 12px; color: var(--text); word-break: break-all; }
  .file-dur { font-size: 11px; color: var(--text-dim); white-space: nowrap; }
  .delete-btn { background: none; border: none; cursor: pointer; color: var(--text-dim); font-size: 14px; padding: 2px 6px; transition: color 0.15s; flex-shrink: 0; }
  .delete-btn:hover { color: var(--red); }
  .delete-btn.marked { color: var(--red); }
  #left-footer { padding: 12px 16px; border-top: 1px solid var(--border); }
  #delete-all-btn { width: 100%; padding: 8px; background: transparent; border: 1px solid var(--red-dim); color: var(--red); font-family: 'Courier New', monospace; font-size: 12px; letter-spacing: 1px; cursor: pointer; transition: all 0.15s; text-transform: uppercase; }
  #delete-all-btn:hover { background: var(--red-dim); color: #fff; }
  #delete-all-btn:disabled { opacity: 0.3; cursor: not-allowed; }

  /* RIGHT PANEL */
  #right { flex: 1; display: flex; flex-direction: column; background: #000; position: relative; min-width: 0; }
  #video-wrapper { flex: 1; display: flex; align-items: center; justify-content: center; background: #000; overflow: hidden; cursor: pointer; }
  video { max-width: 100%; max-height: 100%; display: block; }
  #no-video { color: var(--text-dim); font-size: 13px; letter-spacing: 2px; pointer-events: none; }
  #play-overlay { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 48px; opacity: 0; pointer-events: none; transition: opacity 0.3s; }
  #play-overlay.show { opacity: 1; animation: fadeout 0.6s forwards; }
  @keyframes fadeout { 0% { opacity: 1; } 70% { opacity: 1; } 100% { opacity: 0; } }

  /* PROGRESS AREA */
  #progress-area { background: var(--panel); border-top: 1px solid var(--border); display: flex; flex-direction: column; padding: 10px 16px 10px 16px; gap: 8px; flex-shrink: 0; }

  /* TIMELINE ROW */
  #timeline-row { display: flex; flex-direction: column; width: 100%; position: relative; }
  #time-display { font-size: 10px; color: var(--text-dim); letter-spacing: 1px; margin-bottom: 6px; }

  /* The clickable timeline — full height acts as hit target */
  #progress-container {
    position: relative;
    width: 100%;
    height: 40px;
    cursor: pointer;
    display: flex;
    align-items: center;
  }
  /* Thin visible track inside */
  #progress-track {
    position: absolute;
    left: 0; right: 0;
    height: 6px;
    background: #1c1c1c;
    border-radius: 3px;
    overflow: visible;
  }
  #progress-bar {
    height: 100%;
    background: var(--green-dim);
    border-radius: 3px;
    width: 0%;
    pointer-events: none;
  }
  #progress-head {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 12px; height: 12px;
    border-radius: 50%;
    background: var(--green);
    left: 0%;
    pointer-events: none;
    box-shadow: 0 0 6px var(--green);
    transition: transform 0.1s;
  }
  #progress-container:active #progress-head,
  #progress-container.dragging #progress-head {
    transform: translate(-50%, -50%) scale(1.4);
  }
  /* Brace markers + segment highlights rendered here */
  #markers-layer {
    position: absolute;
    top: 0; left: 0; width: 100%; height: 100%;
    pointer-events: none;
  }
  .segment-highlight {
    position: absolute;
    top: 50%; transform: translateY(-50%);
    height: 6px;
    background: rgba(0,255,65,0.25);
    border-top: 1px solid var(--green-dim);
    border-bottom: 1px solid var(--green-dim);
    pointer-events: none;
  }
  .marker-brace {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    font-size: 18px;
    color: var(--green);
    font-weight: bold;
    pointer-events: none;
    line-height: 1;
    text-shadow: 0 0 6px var(--green);
  }

  /* CONTROLS ROW */
  #controls-row { display: flex; align-items: center; gap: 8px; }
  #controls-left { display: flex; gap: 8px; }
  #controls-right { display: flex; gap: 8px; margin-left: auto; }
  .ctrl-btn {
    padding: 7px 14px;
    background: transparent;
    border: 1px solid var(--green-dim);
    color: var(--green);
    font-family: 'Courier New', monospace;
    font-size: 11px;
    cursor: pointer;
    letter-spacing: 1px;
    text-transform: uppercase;
    transition: all 0.15s;
    white-space: nowrap;
    flex-shrink: 0;
    border-radius: 2px;
    touch-action: manipulation;
  }
  .ctrl-btn:hover { background: var(--green-dark); box-shadow: 0 0 8px var(--green-dim); }
  .ctrl-btn:active { background: var(--green-dim); color: #000; }
  .ctrl-btn.danger { border-color: #664400; color: #cc8800; }
  .ctrl-btn.danger:hover { background: #331f00; box-shadow: 0 0 8px #664400; }

  /* SCANLINE EFFECT */
  body::after { content: ''; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px); pointer-events: none; z-index: 9999; }
</style>
</head>
<body>
<div id="app">
  <!-- LEFT: file list -->
  <div id="left">
    <div id="left-header">▍ VIDEO TERMINAL // DATA</div>
    <div id="file-list"></div>
    <div id="left-footer">
      <button id="delete-all-btn" disabled onclick="confirmDeleteAll()">⚠ 执行删除</button>
    </div>
  </div>

  <!-- RIGHT: player + controls -->
  <div id="right">
    <div id="video-wrapper" onclick="togglePlay()">
      <div id="no-video">// SELECT FILE TO PLAY</div>
      <video id="player" style="display:none" preload="metadata"></video>
      <div id="play-overlay"></div>
    </div>

    <div id="progress-area">
      <!-- Timeline row -->
      <div id="timeline-row">
        <div id="time-display">00:00 / 00:00</div>
        <div id="progress-container">
          <div id="progress-track">
            <div id="progress-bar"></div>
            <div id="progress-head"></div>
          </div>
          <div id="markers-layer"></div>
        </div>
      </div>

      <!-- Controls row -->
      <div id="controls-row">
        <div id="controls-left">
          <button class="ctrl-btn danger" onclick="clearMarkers()">✕ 清除</button>
          <button class="ctrl-btn danger" onclick="undoMarker()">↩ 撤销</button>
        </div>
        <div id="controls-right">
          <button class="ctrl-btn" onclick="markSegment('start')">{ 开始</button>
          <button class="ctrl-btn" onclick="markSegment('end')">结束 }</button>
        </div>
      </div>
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
const fileList = document.getElementById('file-list');
const deleteAllBtn = document.getElementById('delete-all-btn');
const playOverlay = document.getElementById('play-overlay');

let markers = [];
let pendingDeletes = new Set();
let isDragging = false;
let currentFile = null;

function fmtTime(s) {
  s = Math.floor(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h > 0) return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}

function updateProgress() {
  if (!player.duration) return;
  const pct = (player.currentTime / player.duration) * 100;
  progressBar.style.width = pct + '%';
  progressHead.style.left = pct + '%';
  timeDisplay.textContent = fmtTime(player.currentTime) + ' / ' + fmtTime(player.duration);
}

player.addEventListener('timeupdate', updateProgress);
player.addEventListener('loadedmetadata', () => { updateProgress(); renderMarkers(); });

// Play / Pause toggle
function togglePlay() {
  if (!player.src || !player.duration) return;
  if (player.paused) {
    player.play();
    playOverlay.textContent = '▶';
  } else {
    player.pause();
    playOverlay.textContent = '⏸';
  }
  playOverlay.classList.remove('show');
  void playOverlay.offsetWidth; // reflow
  playOverlay.classList.add('show');
}

function seekToPercent(pct) {
  if (!player.duration) return;
  player.currentTime = (pct / 100) * player.duration;
  updateProgress();
}

function getPercent(e) {
  const rect = progressContainer.getBoundingClientRect();
  let pct = ((e.clientX - rect.left) / rect.width) * 100;
  return Math.max(0, Math.min(100, pct));
}

// Touch support helpers
function getTouchPercent(e) {
  const rect = progressContainer.getBoundingClientRect();
  let pct = ((e.touches[0].clientX - rect.left) / rect.width) * 100;
  return Math.max(0, Math.min(100, pct));
}

progressContainer.addEventListener('mousedown', e => {
  isDragging = true;
  progressContainer.classList.add('dragging');
  seekToPercent(getPercent(e));
  e.preventDefault();
});
document.addEventListener('mousemove', e => {
  if (isDragging) seekToPercent(getPercent(e));
});
document.addEventListener('mouseup', () => {
  isDragging = false;
  progressContainer.classList.remove('dragging');
});

progressContainer.addEventListener('touchstart', e => {
  isDragging = true;
  seekToPercent(getTouchPercent(e));
  e.preventDefault();
}, { passive: false });
progressContainer.addEventListener('touchmove', e => {
  if (isDragging) seekToPercent(getTouchPercent(e));
  e.preventDefault();
}, { passive: false });
progressContainer.addEventListener('touchend', () => { isDragging = false; });

// Markers
function markSegment(type) {
  if (!player.src || !player.duration) return;
  markers.push({ type, time: player.currentTime });
  renderMarkers();
}

function undoMarker() {
  if (markers.length === 0) return;
  markers.pop();
  renderMarkers();
}

function clearMarkers() {
  if (markers.length === 0) return;
  if (!confirm('确认清除所有标记？')) return;
  markers = [];
  renderMarkers();
}

function renderMarkers() {
  markersLayer.innerHTML = '';
  if (!player.duration) return;
  const dur = player.duration;

  const starts = markers.filter(m => m.type === 'start').map(m => m.time).sort((a,b) => a-b);
  const ends   = markers.filter(m => m.type === 'end').map(m => m.time).sort((a,b) => a-b);
  const pairs = [];
  let si = 0, ei = 0;
  while (si < starts.length && ei < ends.length) {
    if (ends[ei] > starts[si]) { pairs.push([starts[si], ends[ei]]); si++; ei++; }
    else ei++;
  }

  pairs.forEach(([s, e]) => {
    const el = document.createElement('div');
    el.className = 'segment-highlight';
    el.style.left  = (s / dur * 100) + '%';
    el.style.width = ((e - s) / dur * 100) + '%';
    markersLayer.appendChild(el);
  });

  markers.forEach(m => {
    const el = document.createElement('div');
    el.className = 'marker-brace';
    el.style.left = (m.time / dur * 100) + '%';
    el.textContent = m.type === 'start' ? '{' : '}';
    markersLayer.appendChild(el);
  });
}

// File list
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
  document.querySelectorAll('.file-item').forEach(el => {
    el.classList.toggle('active', el.dataset.name === filename);
  });
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
  if (pendingDeletes.size === 0) return;
  const names = Array.from(pendingDeletes).join('\n');
  if (!confirm(`确认删除以下 ${pendingDeletes.size} 个文件？\n\n${names}`)) return;
  fetch('/delete', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({files: Array.from(pendingDeletes)})
  }).then(r => r.json()).then(data => {
    if (data.ok) { pendingDeletes.clear(); loadFileList(); }
    else alert('删除失败: ' + (data.error || ''));
  });
}

function loadFileList() {
  fetch('/files').then(r => r.json()).then(files => {
    fileList.innerHTML = '';
    files.forEach(f => {
      const item = document.createElement('div');
      item.className = 'file-item';
      item.dataset.name = f.name;
      if (f.name === currentFile) item.classList.add('active');
      const safeName = f.name.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
      item.innerHTML = `
        <span class="file-name">${f.name}</span>
        <span class="file-dur">${f.duration}</span>
        <button class="delete-btn" title="标记删除" onclick="event.stopPropagation();toggleDelete('${safeName}',this)">🗑</button>
      `;
      item.addEventListener('click', () => loadFile(f.name));
      fileList.appendChild(item);
    });
  });
}

loadFileList();
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
            mtime = os.path.getmtime(fp)
            dur = get_video_duration(fp)
            files.append({'name': f, 'mtime': mtime, 'duration': dur})
    files.sort(key=lambda x: x['mtime'], reverse=True)
    return jsonify(files)

@app.route('/video/<filename>')
def serve_video(filename):
    safe = os.path.basename(filename)
    fp = os.path.join(DATA_DIR, safe)
    if not os.path.exists(fp):
        abort(404)
    return send_from_directory(DATA_DIR, safe, conditional=True)

@app.route('/delete', methods=['POST'])
def delete_files():
    data = request.get_json()
    errors = []
    for name in data.get('files', []):
        safe = os.path.basename(name)
        fp = os.path.join(DATA_DIR, safe)
        try:
            if os.path.exists(fp):
                os.remove(fp)
        except Exception as e:
            errors.append(str(e))
    if errors:
        return jsonify({'ok': False, 'error': '; '.join(errors)})
    return jsonify({'ok': True})

if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
