# Video Player

Local video course player with Python backend and HTML5 frontend. Play any folder of videos as a structured course with chapters, progress tracking, and document viewing.

## Features

- **Native HTML5 video player** with speed control (0.5x - 2x), subtitles, and keyboard shortcuts
- **Automatic chapter detection** from folder structure
- **Smart ordering** - numbers at start/end of filenames, "Módulo 1" format, items starting with "-" go to bottom
- **Progress tracking** - resume from last position, completion percentage per chapter
- **Document viewer** - PDF, images, text, JSON, ZIP files
- **Multi-instance support** - run multiple courses simultaneously (ports 8002-8020)
- **Duration caching** - fast startup with background calculation
- **Resizable sidebar** with tooltips for full filenames

## Installation

1. Place `ffprobe.exe` in `scanner/bin/` (required for video duration)
2. Run `install.bat` as Administrator to add Windows Explorer context menu
3. Right-click any folder containing videos and select "Play Course"

## Usage

### From Context Menu
Right-click a folder → "Play Course"

### From Command Line
```batch
runner.bat "C:\path\to\course"
```

### Manual Start
```batch
python server.py --port 8002 --path "C:\path\to\course"
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Play/Pause |
| ← / → | Seek ±10s |
| ↑ / ↓ | Volume ±10% |
| Shift+N | Next video |
| Shift+P | Previous video |
| F | Fullscreen |
| M | Mute toggle |

## File Ordering Rules

Files and folders are sorted by extracted numbers:

1. Number at START: `1_intro.mp4`, `01 - Setup.mp4`, `[1] Welcome`
2. "Word Number" format: `Módulo 1`, `Chapter 10`
3. Number at END: `intro_1.mp4`, `lesson - 01.mp4`
4. Items starting with `-`: sorted by creation date, placed at bottom
5. No number: alphabetical, at the very bottom

## Supported Formats

- **Video**: mp4, mkv, webm, avi, mov, m4v
- **Subtitles**: srt, vtt
- **Documents**: pdf, txt, json, zip, rar, 7z, md, html
- **Images**: jpg, jpeg, png, gif, webp, bmp, svg

## Project Structure

```
video-player/
├── server.py              # Python HTTP server + API
├── runner.bat             # Multi-instance launcher
├── install.bat            # Windows context menu setup
├── uninstall.bat          # Remove context menu
├── scanner/
│   ├── directory.py       # Recursive directory scanner
│   ├── ordering.py        # Number extraction + sorting
│   └── model.py           # Data classes
└── web/
    ├── index.html         # Main UI
    ├── css/player.css     # Dark theme styling
    └── js/
        ├── app.js         # Main app + state
        ├── player.js      # Video playback
        ├── playlist.js    # Sidebar navigation
        ├── progress.js    # localStorage tracking
        └── modal.js       # Document viewer
```

## Requirements

- Python 3.8+
- ffprobe (for video duration)
- Modern web browser

## Uninstall

Run `uninstall.bat` as Administrator to remove the context menu entry.
