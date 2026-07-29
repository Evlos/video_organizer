# durationCache.py
import os
import json
import subprocess
import threading

CACHE_LOCK = threading.Lock()

def getDurationCachePath(dataDir):
    return os.path.join(dataDir, '.durationCache.json')

def loadDurationCache(dataDir):
    cachePath = getDurationCachePath(dataDir)
    if not os.path.exists(cachePath):
        return {}
    try:
        with open(cachePath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[durationCache] load failed, resetting cache: {e}")
        return {}

def saveDurationCache(dataDir, cache):
    cachePath = getDurationCachePath(dataDir)
    tmpPath = cachePath + '.tmp'
    try:
        with open(tmpPath, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmpPath, cachePath)
    except Exception as e:
        print(f"[durationCache] save failed: {e}")

def probeDurationRaw(filepath):
    print(f"[durationCache] ffprobe MISS, running for: {filepath}")
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
    except Exception as e:
        print(f"[durationCache] ffprobe failed for {filepath}: {e}")
        return "--:--"

def getCachedDuration(dataDir, filename, filepath, cache):
    try:
        stat = os.stat(filepath)
        cacheKey = f"{filename}:{stat.st_mtime}:{stat.st_size}"
    except OSError as e:
        print(f"[durationCache] stat failed for {filepath}: {e}")
        return "--:--", False

    entry = cache.get(filename)
    if entry and entry.get('key') == cacheKey:
        print(f"[durationCache] HIT for {filename}")
        return entry['duration'], False

    duration = probeDurationRaw(filepath)
    cache[filename] = {'key': cacheKey, 'duration': duration}
    return duration, True

def getDurationsForFiles(dataDir, filenames):
    with CACHE_LOCK:
        cache = loadDurationCache(dataDir)
        dirty = False
        results = {}
        for filename in filenames:
            filepath = os.path.join(dataDir, filename)
            duration, changed = getCachedDuration(dataDir, filename, filepath, cache)
            results[filename] = duration
            dirty = dirty or changed

        staleKeys = [k for k in cache if k not in filenames]
        for k in staleKeys:
            print(f"[durationCache] evicting stale cache entry: {k}")
            del cache[k]
            dirty = True

        if dirty:
            saveDurationCache(dataDir, cache)

        return results
