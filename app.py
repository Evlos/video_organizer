# app.py
import os
import json
import re
import subprocess
import configparser
from flask import Flask, render_template, send_from_directory, jsonify, request, abort

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

@app.route('/')
def index():
    return render_template("index.html")

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
