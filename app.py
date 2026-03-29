# app.py
import os
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
  }
  html, body { height: 100%; background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; overflow: hidden; }
  #app { display: flex; height: 100vh; }

  /* LEFT */
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
  .del-btn { background: none; border: none; cursor: pointer; color: var(--text-dim); font-size: 14px; padding: 2px 6px; transition: color 0.15s; flex-shrink: 0; }
  .del-btn:hover { color: var(--red); }
  .del-btn.marked { color: var(--red); }
  #left-footer { padding: 12px 16px; border-top: 1px solid var(--border); }
  #delete-all-btn { width: 100%; padding: 8px; background: transparent; border: 1px solid var(--red-dim); color: var(--red); font-family: 'Courier New', monospace; font-size: 12px; letter-spacing: 1px; cursor: pointer; transition: all 0.15s; text-transform: uppercase; }
  #delete-all-btn:hover:not(:disabled) { background: var(--red-dim); color: #fff; }
  #delete-all-btn:disabled { opacity: 0.3; cursor: not-allowed; }

  /* RIGHT */
  #right { flex: 1; display: flex; flex-direction: column; background: #000; }
  #video-wrapper { flex: 1; display: flex; align-items: center; justify-content: center; background: #000; overflow: hidden; min-height: 0; }
  #player { max-width: 100%; max-height: 100%; display: none; }
  #no-video { color: var(--text-dim); font-size: 13px; letter-spacing: 2px; }

  /* PROGRESS */
  #progress-area { height: 80px; background: var(--panel); border-top: 1px solid var(--border); display: flex; align-items: center; padding: 0 16px; gap: 12px; flex-shrink: 0; }
  #progress-container { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: center; position: relative; }
  #time-display { font-size: 10px; color: var(--text-dim); letter-spacing: 1px; margin-bottom: 10px; }
  #progress-track { height: 6px; background: #1a1a1a; border-radius: 3px; position: relative; cursor: pointer; }
  #progress-fill { height: 100%; background: var(--green-dim); border-radius: 3px; width: 0%; pointer-events: none; }
  #progress-head { position: absolute; top: 50%; transform: translate(-50%, -50%); width: 10px; height: 10px; border-radius: 50%; background: var(--green); left: 0%; pointer-events: none; box-shadow: 0 0 6px var(--green); }
  #markers-layer { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
  .seg-hi { position: absolute; top: -5px; height: 16px; background: rgba(0,255,65,0.15); border-top: 1px solid var(--green-dim); border-bottom: 1px solid var(--green-dim); }
  .brace { position: absolute; top: -20px; font-size: 14px; color: var(--green); transform: translateX(-50%); font-weight: bold; line-height: 1; }
  .ctrl-btn { padding: 8px 14px; background: transparent; border: 1px solid var(--green-dim); color: var(--green); font-family: 'Courier New', monospace; font-size: 11px; cursor: pointer; letter-spacing: 1px; text-transform: uppercase; transition: all 0.15s; white-space: nowrap; flex-shrink: 0; }
  .ctrl-btn:hover { background: var(--green-dark); box-shadow: 0 0 8px var(--green-dim); }

  body::after { content: ''; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px); pointer-events: none; z-index: 9999; }
</style>
</head>
<body>
<div id="app">
  <div id="left">
    <div id="left-header">&#9613; VIDEO TERMINAL // DATA</div>
    <div id="file-list"></div>
    <div id="left-footer">
      <button id="delete-all-btn" disabled>&#9888; 执行删除</button>
    </div>
  </div>
  <div id="right">
    <div id="video-wrapper">
      <div id="no-video">// SELECT FILE TO PLAY</div>
      <video id="player" preload="metadata"></video>
    </div>
    <div id="progress-area">
      <div id="progress-container">
        <div id="time-display">00:00 / 00:00</div>
        <div id="progress-track">
          <div id="progress-fill"></div>
          <div id="progress-head"></div>
          <div id="markers-layer"></div>
        </div>
      </div>
      <button class="ctrl-btn" id="btn-start">{ 开始</button>
      <button class="ctrl-btn" id="btn-end">结束 }</button>
    </div>
  </div>
</div>

<script>
(function() {
  var player = document.getElementById('player');
  var progressFill = document.getElementById('progress-fill');
  var progressHead = document.getElementById('progress-head');
  var progressTrack = document.getElementById('progress-track');
  var markersLayer = document.getElementById('markers-layer');
  var timeDisplay = document.getElementById('time-display');
  var fileListEl = document.getElementById('file-list');
  var deleteAllBtn = document.getElementById('delete-all-btn');
  var noVideo = document.getElementById('no-video');

  var markers = [];
  var pendingDeletes = {};
  var isDragging = false;
  var currentFile = null;

  function fmtTime(s) {
    s = Math.floor(s || 0);
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    var mm = m < 10 ? '0' + m : '' + m;
    var ss = sec < 10 ? '0' + sec : '' + sec;
    if (h > 0) {
      var hh = h < 10 ? '0' + h : '' + h;
      return hh + ':' + mm + ':' + ss;
    }
    return mm + ':' + ss;
  }

  function updateProgress() {
    if (!player.duration) return;
    var pct = (player.currentTime / player.duration) * 100;
    progressFill.style.width = pct + '%';
    progressHead.style.left = pct + '%';
    timeDisplay.textContent = fmtTime(player.currentTime) + ' / ' + fmtTime(player.duration);
  }

  player.addEventListener('timeupdate', updateProgress);
  player.addEventListener('loadedmetadata', function() {
    updateProgress();
    renderMarkers();
  });

  function seekToPercent(pct) {
    if (!player.duration) return;
    if (pct < 0) pct = 0;
    if (pct > 100) pct = 100;
    player.currentTime = (pct / 100) * player.duration;
    updateProgress();
  }

  function getPct(e) {
    var rect = progressTrack.getBoundingClientRect();
    return ((e.clientX - rect.left) / rect.width) * 100;
  }

  progressTrack.addEventListener('mousedown', function(e) {
    isDragging = true;
    seekToPercent(getPct(e));
    e.preventDefault();
  });
  document.addEventListener('mousemove', function(e) {
    if (isDragging) seekToPercent(getPct(e));
  });
  document.addEventListener('mouseup', function() { isDragging = false; });

  function markSegment(type) {
    if (!player.src || !player.duration) return;
    markers.push({ type: type, time: player.currentTime });
    renderMarkers();
  }

  function renderMarkers() {
    markersLayer.innerHTML = '';
    if (!player.duration) return;
    var dur = player.duration;
    var starts = [];
    var ends = [];
    for (var i = 0; i < markers.length; i++) {
      if (markers[i].type === 'start') starts.push(markers[i].time);
      else ends.push(markers[i].time);
    }
    starts.sort(function(a,b){return a-b;});
    ends.sort(function(a,b){return a-b;});

    var si = 0, ei = 0;
    while (si < starts.length && ei < ends.length) {
      if (ends[ei] > starts[si]) {
        var el = document.createElement('div');
        el.className = 'seg-hi';
        el.style.left = (starts[si]/dur*100) + '%';
        el.style.width = ((ends[ei]-starts[si])/dur*100) + '%';
        markersLayer.appendChild(el);
        si++; ei++;
      } else {
        ei++;
      }
    }

    for (var j = 0; j < markers.length; j++) {
      var b = document.createElement('div');
      b.className = 'brace';
      b.style.left = (markers[j].time/dur*100) + '%';
      b.textContent = markers[j].type === 'start' ? '{' : '}';
      markersLayer.appendChild(b);
    }
  }

  function loadFile(filename) {
    currentFile = filename;
    markers = [];
    markersLayer.innerHTML = '';
    progressFill.style.width = '0%';
    progressHead.style.left = '0%';
    timeDisplay.textContent = '00:00 / 00:00';
    noVideo.style.display = 'none';
    player.style.display = 'block';
    player.src = '/video/' + encodeURIComponent(filename);
    player.play();
    var items = fileListEl.querySelectorAll('.file-item');
    for (var i = 0; i < items.length; i++) {
      if (items[i].getAttribute('data-name') === filename) {
        items[i].classList.add('active');
      } else {
        items[i].classList.remove('active');
      }
    }
  }

  function toggleDelete(filename, btn) {
    if (pendingDeletes[filename]) {
      delete pendingDeletes[filename];
      btn.classList.remove('marked');
      btn.closest('.file-item').classList.remove('pending-delete');
    } else {
      pendingDeletes[filename] = true;
      btn.classList.add('marked');
      btn.closest('.file-item').classList.add('pending-delete');
    }
    deleteAllBtn.disabled = Object.keys(pendingDeletes).length === 0;
  }

  function confirmDeleteAll() {
    var files = Object.keys(pendingDeletes);
    if (files.length === 0) return;
    if (!confirm('确认删除以下 ' + files.length + ' 个文件？\n\n' + files.join('\n'))) return;
    fetch('/delete', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({files: files})
    }).then(function(r){ return r.json(); }).then(function(data) {
      if (data.ok) {
        pendingDeletes = {};
        deleteAllBtn.disabled = true;
        loadFileList();
      } else {
        alert('删除失败: ' + (data.error || '未知错误'));
      }
    });
  }

  function loadFileList() {
    fetch('/files').then(function(r){ return r.json(); }).then(function(files) {
      fileListEl.innerHTML = '';
      for (var i = 0; i < files.length; i++) {
        (function(f) {
          var item = document.createElement('div');
          item.className = 'file-item';
          if (pendingDeletes[f.name]) item.classList.add('pending-delete');
          if (f.name === currentFile) item.classList.add('active');
          item.setAttribute('data-name', f.name);

          var nameSpan = document.createElement('span');
          nameSpan.className = 'file-name';
          nameSpan.textContent = f.name;

          var durSpan = document.createElement('span');
          durSpan.className = 'file-dur';
          durSpan.textContent = f.duration;

          var delBtn = document.createElement('button');
          delBtn.className = 'del-btn';
          if (pendingDeletes[f.name]) delBtn.classList.add('marked');
          delBtn.title = '标记删除';
          delBtn.textContent = '\uD83D\uDDD1';
          delBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleDelete(f.name, delBtn);
          });

          item.appendChild(nameSpan);
          item.appendChild(durSpan);
          item.appendChild(delBtn);
          item.addEventListener('click', function() { loadFile(f.name); });
          fileListEl.appendChild(item);
        })(files[i]);
      }
    });
  }

  document.getElementById('btn-start').addEventListener('click', function() { markSegment('start'); });
  document.getElementById('btn-end').addEventListener('click', function() { markSegment('end'); });
  deleteAllBtn.addEventListener('click', confirmDeleteAll);

  loadFileList();
})();
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
