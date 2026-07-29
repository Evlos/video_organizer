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

def buildContentKey(filepath):
    # key由文件内容特征(mtime+size)组成，不含文件名，重命名后依然命中
    stat = os.stat(filepath)
    return f"{stat.st_size}:{int(stat.st_mtime)}"

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

def getDurationsForFiles(dataDir, filenames):
    with CACHE_LOCK:
        cache = loadDurationCache(dataDir)
        dirty = False
        results = {}
        activeKeys = set()

        for filename in filenames:
            filepath = os.path.join(dataDir, filename)
            try:
                contentKey = buildContentKey(filepath)
            except OSError as e:
                print(f"[durationCache] stat failed for {filepath}: {e}")
                results[filename] = "--:--"
                continue

            activeKeys.add(contentKey)

            if contentKey in cache:
                print(f"[durationCache] HIT for {filename} (key={contentKey})")
                results[filename] = cache[contentKey]
            else:
                duration = probeDurationRaw(filepath)
                cache[contentKey] = duration
                results[filename] = duration
                dirty = True

        staleKeys = [k for k in cache if k not in activeKeys]
        for k in staleKeys:
            print(f"[durationCache] evicting stale cache entry: key={k}")
            del cache[k]
            dirty = True

        if dirty:
            saveDurationCache(dataDir, cache)

        return results
