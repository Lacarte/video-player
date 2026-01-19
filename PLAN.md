# Video Player - Project Plan

## Overview

Local video course player with Python backend and HTML5 frontend.
Supports multiple simultaneous instances via dynamic port allocation.

---

## System Architecture

```
Windows Explorer
  └─ Right click folder
       └─ "Play Course"
            └─ runner.bat
                 └─ Find free port (8002-8020)
                      └─ Python server
                           ├─ Scan + order files
                           ├─ Build playlist JSON
                           └─ Serve UI + media
                                └─ HTML / CSS / JS Player
```

---

## Project Structure

```
video-player/
├── install.bat              # Registry setup (admin)
├── uninstall.bat            # Registry removal
├── runner.bat               # Multi-instance launcher
├── server.py                # Python HTTP server + API
│
├── scanner/
│   ├── __init__.py
│   ├── directory.py         # Recursive directory walker
│   ├── ordering.py          # Number extraction + sorting
│   └── model.py             # Data classes for nodes
│
└── web/
    ├── index.html           # Main UI (single page)
    ├── css/
    │   └── player.css       # Dark theme styling
    └── js/
        ├── app.js           # Main app state + init
        ├── player.js        # Video playback + resume
        ├── playlist.js      # Sidebar navigation
        ├── progress.js      # localStorage tracking
        └── modal.js         # Document viewer
```

---

## Modules

### 1. Windows Context Menu (`install.bat`)

- Registry key: `HKCR\Directory\shell\PlayCourse`
- Display name: "Play Course"
- Icon: shell32.dll,176
- Requires admin rights

### 2. Runner (`runner.bat`)

- Accepts folder path as argument
- Finds available port in range 8002-8020
- Starts Python server
- Opens browser automatically

### 3. Python Server (`server.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve index.html |
| `/api/playlist` | GET | Course structure JSON |
| `/media/*` | GET | Videos, docs, subtitles (Range support) |
| `/static/*` | GET | CSS/JS files |

### 4. Directory Scanner (`scanner/directory.py`)

- Recursive scan (unlimited depth)
- Folder = chapter
- File types:
  - Video: mp4, mkv, webm, avi, mov
  - Subtitles: srt, vtt
  - Documents: pdf, txt, json, zip, images

### 5. Ordering Engine (`scanner/ordering.py`)

Rules per folder level:
1. Extract number at START: `1_intro.mp4` → order 1
2. If not found, number at END: `intro_1.mp4` → order 1
3. No number → push to bottom (order 999999)
4. Same number → alphabetical sort

### 6. Data Model (`scanner/model.py`)

```json
{
  "type": "course",
  "title": "Course Name",
  "root_path": "C:/path/to/course",
  "port": 8002,
  "total_duration": 18420,
  "total_videos": 25,
  "chapters": [
    {
      "type": "chapter",
      "title": "Chapter 1",
      "order": 1,
      "duration": 3600,
      "videos": [...],
      "documents": [...],
      "children": [...]
    }
  ]
}
```

---

## Frontend Features

### UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Header: Course Title                          [Stats: videos]  │
├────────────────┬────────────────────────────────┬───────────────┤
│   PLAYLIST     │       VIDEO PLAYER             │  DOCUMENTS    │
│   (sidebar)    │       (native HTML5)           │  (per chapter)│
│                │                                │               │
│  ▼ Chapter 1   │   ┌────────────────────────┐   │  📄 notes.pdf │
│    • Lesson 1  │   │      <video>           │   │  🖼 image.png │
│    • Lesson 2  │   └────────────────────────┘   │               │
│  ▶ Chapter 2   │                                │               │
│                │   [◄◄] [▶] [►►] [Speed] [CC]   │               │
└────────────────┴────────────────────────────────┴───────────────┘
```

### Video Player (`player.js`)

- Native HTML5 `<video>` controls
- Speed control (0.5x - 2x)
- Subtitle selector (native `<track>`)
- Resume from last position
- Auto-play next video
- Keyboard shortcuts

### Progress Tracking (`progress.js`)

Stored in `localStorage`:
- `video_player:progress:<path>` - Current position (seconds)
- `video_player:completed:<path>` - Completion flag
- `video_player:last_watched:<course>` - Resume point
- `video_player:playback_speed` - User preference
- `video_player:autoplay` - User preference

Completion rule: Video marked complete at ≥90% watched

### Document Modal (`modal.js`)

Supports:
- 📕 PDF (iframe)
- 🖼 Images (inline)
- 📝 Text/Markdown (pre-formatted)
- 📋 JSON (formatted)
- 📦 ZIP (download only)

---

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

---

## Multi-Instance Support

- Port range: 8002-8020 (18 simultaneous courses)
- Each launch finds next available port
- No lock files needed
- Browser tabs show course name for identification

---

## Constraints

- ❌ No export
- ❌ No accounts/auth
- ❌ No database
- ❌ No cloud sync
- ❌ No build tools (npm, webpack)
- ✅ Pure HTML/CSS/JS
- ✅ Python stdlib only
- ✅ Offline/local only
- ✅ Browser localStorage for persistence

---

## Build Order (MVP)

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Python server + scanner modules | ✅ |
| 2 | Playlist JSON endpoint | ✅ |
| 3 | Basic HTML layout | ✅ |
| 4 | Video playback + controls | ✅ |
| 5 | Resume logic | ✅ |
| 6 | Subtitle support | ✅ |
| 7 | Document modal | ✅ |
| 8 | Progress tracking | ✅ |
| 9 | Windows registry install | ✅ |
| 10 | Multi-instance support | ✅ |

---

## Usage

1. Run `install.bat` as administrator
2. Right-click any folder containing videos
3. Select "Play Course"
4. Browser opens with video player
5. Progress saved automatically

To uninstall: Run `uninstall.bat` as administrator
