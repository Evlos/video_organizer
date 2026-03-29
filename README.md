# 🖥️ VIDEO ORGANIZER

> A minimal dark-style web video manager built with Flask — browse, play, annotate, and organize your local MP4 library from any browser or iPad.

---

## Preview

![Preview](https://raw.githubusercontent.com/Evlos/uploads/refs/heads/main/VIDEO%20TERMINAL%20-%20Google%20Chrome_2026-03-29_14-15-05.jpg)

---

## ✨ Features

- **Dark UI** with scanline aesthetic and green-on-black color scheme
- **File browser** — lists all `.mp4` files in the `data/` folder, sorted by modification time (newest first), with duration display
- **Click-to-play** — select any file to load and play in the right panel; click the video to toggle play/pause
- **Timeline scrubber** — large 40px hit-area progress bar with drag support (mouse & touch); click or drag anywhere to seek
- **Segment markers** — mark `{` start and `}` end points at the current playback position; matched pairs are highlighted on the timeline; supports multiple segments, undo (last marker), and clear all (with confirmation)
- **Auto-save markers** — markers are saved to a `.json` sidecar file alongside the video on every change; lonely start markers are auto-paired with the video end, lonely end markers with `0:00`
- **JSON indicator** — files with saved marker data show a `◈` icon in the file list
- **Rename workflow** — prefix a video with a custom string (e.g. `1b2k`); the prefix is parsed into reusable tags (`1b`, `2k`) stored in `config.ini` and shown as clickable chips in the rename dialog
- **Trash & bulk delete** — mark files for deletion with the 🗑 icon; a confirmation dialog lists all pending files before permanent removal (sidecar `.json` files are also deleted)

---

## 🚀 Getting Started

### Method 1: GitHub Container Registry (Simplest)

```bash
# Pull and run the pre-built image directly
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  --name video_organizer \
  ghcr.io/evlos/video_organizer:latest
```

Visit [http://localhost:5000](http://localhost:5000) to start using the app.

### Method 2: Run Locally

#### Prerequisites

- Python 3.7+
- [FFmpeg](https://ffmpeg.org/) (for video duration detection)

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```


#### Installation

```bash
git clone https://github.com/Evlos/video_organizer.git
cd video_organizer
pip install flask
```


#### Run

```bash
python app.py
```

Then open your browser at **http://localhost:5000**

> Place your `.mp4` files inside the `data/` directory (created automatically on first run).

---

## 📁 Project Structure

```
video-organizer/
├── app.py        # Flask backend — file listing, video streaming, deletion API
└── data/         # Drop your .mp4 files here
```


---

## 🎮 Usage

| Action | How |
| :-- | :-- |
| Play a video | Click a filename in the left panel |
| Seek | Click anywhere on the progress bar |
| Scrub | Click and drag along the progress bar |
| Mark segment start | Click **{ Mark In** button during playback |
| Mark segment end | Click **Mark Out }** button during playback |
| Mark file for deletion | Click the 🗑 icon next to a filename |
| Delete marked files | Click **⚠ PURGE**, then confirm |


---

## ⚙️ Configuration

| Variable | Default | Description |
| :-- | :-- | :-- |
| `DATA_DIR` | `./data` | Directory scanned for `.mp4` files |
| `host` | `0.0.0.0` | Server bind address |
| `port` | `5000` | Server port |

Edit the bottom of `app.py` to change these values.

---

## 🛡️ Security Notes

- File paths are sanitized with `os.path.basename()` to prevent directory traversal attacks
- Only `.mp4` files are listed and served; other file types are ignored

---

## 📦 Dependencies

| Package | Purpose |
| :-- | :-- |
| `flask` | Web framework \& file serving |
| `ffprobe` | Video duration detection (via subprocess) |


---

## 📄 License

This project is open-sourced under the [GNU General Public License v3.0](LICENSE).
