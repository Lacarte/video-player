#!/usr/bin/env python3
"""
Video Player Server
Serves course content with playlist API and media streaming.
Supports multiple instances via dynamic port assignment.
"""

import http.server
import socketserver
import os
import sys
import json
import argparse
import re
import mimetypes
import subprocess
import threading
from pathlib import Path
from urllib.parse import unquote, quote

from loguru import logger

# Add scanner module to path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

# Configure loguru
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    level="INFO"
)
logger.add(
    LOG_DIR / "server_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    level="DEBUG"
)

from scanner.directory import scan_directory, calculate_duration_for_video
from scanner.model import NodeEncoder

# Configuration
DEFAULT_PORT = 8002
MAX_PORT = 8020

# MIME types
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('video/x-matroska', '.mkv')
mimetypes.add_type('video/mp2t', '.ts')
mimetypes.add_type('video/mp2t', '.mts')
mimetypes.add_type('video/mp2t', '.m2ts')
mimetypes.add_type('video/quicktime', '.mov')
mimetypes.add_type('text/vtt', '.vtt')
mimetypes.add_type('application/x-subrip', '.srt')


# ── Video compatibility check and conversion ──────────────────────────

# Compatible containers (as reported by ffprobe format_name)
COMPATIBLE_CONTAINERS = {'mov,mp4,m4a,3gp,3g2,mj2'}

# Incompatible H.264 profiles (10-bit, 4:2:2, etc.)
INCOMPATIBLE_H264_PROFILES = {'high 10', 'high 4:2:2', 'high 4:4:4',
                               'high 10 intra', 'high 4:2:2 intra', 'high 4:4:4 intra',
                               'high 4:4:4 predictive'}

# Browser-compatible codecs (no re-encoding needed if container is the only issue)
BROWSER_COMPATIBLE_CODECS = {'h264', 'aac', 'mp3', 'opus', 'flac'}

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.avi', '.mov', '.m4v', '.ts', '.mts', '.m2ts'}

# Global conversion state (read by /api/conversion-status)
_conversion_state = {
    'phase': '',           # 'scanning', 'waiting', 'converting', 'done'
    'current_file': '',
    'current_index': 0,
    'total': 0,
    'percent': 0,          # progress within current file (0-100)
    'done_count': 0,
    'failed_count': 0,
    'files': [],           # list of {name, size_mb, mode} for the dialog
}

# Internal list of (Path, mode) pairs — set by scan, used by convert
_to_convert = []
_course_path_for_convert = None


def _probe_video(file_path: Path) -> dict:
    """Run ffprobe on a file and return parsed JSON, or empty dict on failure."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', str(file_path)],
            capture_output=True, text=True, encoding='utf-8',
            errors='ignore', timeout=15
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return {}


def check_video_compatibility(file_path: Path) -> str:
    """Check if a video file is browser-compatible.
    Returns: 'compatible', 'remux' (container fix only), or 'transcode' (re-encode needed).
    """
    data = _probe_video(file_path)
    if not data:
        return 'compatible'  # Can't probe → assume OK

    fmt = data.get('format', {}).get('format_name', '')
    bad_container = fmt not in COMPATIBLE_CONTAINERS

    needs_reencode = False
    for stream in data.get('streams', []):
        codec = stream.get('codec_name', '').lower()
        codec_type = stream.get('codec_type', '')

        if codec_type == 'video':
            profile = stream.get('profile', '').lower()
            pix_fmt = stream.get('pix_fmt', '').lower()

            if codec == 'h264':
                if profile in INCOMPATIBLE_H264_PROFILES:
                    needs_reencode = True
                elif '10le' in pix_fmt or '10be' in pix_fmt:
                    needs_reencode = True
            elif codec not in BROWSER_COMPATIBLE_CODECS:
                needs_reencode = True

    if needs_reencode:
        return 'transcode'
    elif bad_container:
        return 'remux'
    return 'compatible'


def _check_nvenc_available() -> bool:
    """Check if NVIDIA NVENC hardware encoder actually works."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-f', 'lavfi', '-i', 'nullsrc=s=64x64:d=0.1',
             '-c:v', 'h264_nvenc', '-f', 'null', '-'],
            capture_output=True, text=True, encoding='utf-8',
            errors='ignore', timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def _verify_converted(original: Path, converted: Path) -> bool:
    """Verify a converted file is valid by comparing with the original.
    Checks: file exists, size > 0, has video+audio streams, duration within 2s of original.
    """
    if not converted.exists():
        logger.debug(f"  Verify: converted file does not exist: {converted}")
        return False
    if converted.stat().st_size == 0:
        logger.debug(f"  Verify: converted file is empty: {converted}")
        return False

    orig_data = _probe_video(original)
    conv_data = _probe_video(converted)

    if not conv_data:
        logger.debug(f"  Verify: ffprobe failed on converted file")
        return False

    # Must have at least one video stream
    conv_streams = {s.get('codec_type') for s in conv_data.get('streams', [])}
    if 'video' not in conv_streams:
        logger.debug(f"  Verify: no video stream in converted file (streams: {conv_streams})")
        return False

    # Duration must be within 2 seconds of original
    orig_dur = float(orig_data.get('format', {}).get('duration', 0))
    conv_dur = float(conv_data.get('format', {}).get('duration', 0))
    if orig_dur > 0 and abs(orig_dur - conv_dur) > 2.0:
        logger.debug(f"  Verify: duration mismatch orig={orig_dur:.2f}s conv={conv_dur:.2f}s diff={abs(orig_dur - conv_dur):.2f}s")
        return False

    # Container must now be MP4
    conv_fmt = conv_data.get('format', {}).get('format_name', '')
    if conv_fmt not in COMPATIBLE_CONTAINERS:
        logger.debug(f"  Verify: wrong container '{conv_fmt}' (expected one of {COMPATIBLE_CONTAINERS})")
        return False

    return True


def _get_duration_seconds(file_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    data = _probe_video(file_path)
    return float(data.get('format', {}).get('duration', 0))


def _progress_bar(pct: int, width: int = 30) -> str:
    """Build a text progress bar like [============..................]"""
    pct = max(0, min(100, pct))
    filled = int(width * pct / 100)
    empty = width - filled
    bar = '=' * filled + '.' * empty
    return f'[{bar}]'


def _run_ffmpeg_with_progress(cmd: list, duration: float, label: str) -> tuple:
    """Run ffmpeg with real-time progress bar on stdout.
    Returns (returncode, stderr_text).
    """
    # Add -progress pipe:1 for machine-readable progress
    cmd_with_progress = cmd[:]
    output_file = cmd_with_progress.pop()
    cmd_with_progress.extend(['-progress', 'pipe:1', output_file])

    proc = subprocess.Popen(
        cmd_with_progress,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Drain stderr in a background thread to prevent pipe deadlock.
    # If stderr buffer fills up while we're reading stdout, ffmpeg blocks
    # and both processes deadlock.
    stderr_chunks = []
    def drain_stderr():
        for chunk in proc.stderr:
            stderr_chunks.append(chunk)
    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()

    last_pct = -1
    for line in proc.stdout:
        line = line.decode('utf-8', errors='ignore').strip()
        if line.startswith('out_time_us=') and duration > 0:
            try:
                time_us = int(line.split('=', 1)[1])
                if time_us < 0:
                    continue
                pct = max(0, min(99, int((time_us / 1_000_000) / duration * 100)))
                if pct != last_pct:
                    last_pct = pct
                    _conversion_state['percent'] = pct
                    bar = _progress_bar(pct)
                    print(f'\r  {bar} {pct:3d}% {label}', end='', flush=True)
            except (ValueError, ZeroDivisionError):
                pass

    proc.wait()
    stderr_thread.join(timeout=5)

    # Complete the progress bar
    if last_pct >= 0:
        bar = _progress_bar(100)
        print(f'\r  {bar} 100% {label}', flush=True)

    stderr = b''.join(stderr_chunks).decode('utf-8', errors='ignore')
    return proc.returncode, stderr


def scan_videos_on_startup(course_path: Path) -> None:
    """Scan course directory for incompatible videos.
    Sets phase to 'waiting' with a file list if any are found.
    Runs in a background thread so the server is immediately available.
    """
    global _to_convert, _course_path_for_convert
    _course_path_for_convert = course_path
    _conversion_state['phase'] = 'scanning'
    logger.info("Scanning for incompatible video formats...")

    # Collect all video files
    video_files = []
    for root, dirs, files in os.walk(course_path):
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules',
                   '.vscode', 'trash', 'deleteVideos', '.idea', '.transcoded'}]
        for f in files:
            if Path(f).suffix.lower() in VIDEO_EXTENSIONS:
                video_files.append(Path(root) / f)

    if not video_files:
        logger.info("No video files found.")
        _conversion_state['phase'] = 'done'
        return

    # Check compatibility for each with progress
    to_convert = []
    total = len(video_files)
    _conversion_state['total'] = total
    for idx, vf in enumerate(video_files):
        pct = int((idx + 1) / total * 100)
        _conversion_state['current_index'] = idx + 1
        _conversion_state['percent'] = pct
        bar = _progress_bar(pct)
        print(f'\r  {bar} {pct:3d}% Checking {idx + 1}/{total} videos...', end='', flush=True)
        compat = check_video_compatibility(vf)
        if compat != 'compatible':
            to_convert.append((vf, compat))
    print(f'\r  {_progress_bar(100)} 100% Checked {total} videos.          ', flush=True)

    if not to_convert:
        logger.info("All videos are browser-compatible.")
        _conversion_state['phase'] = 'done'
        return

    # Store for later conversion
    _to_convert = to_convert

    # Count and log
    remux_count = sum(1 for _, m in to_convert if m == 'remux')
    transcode_count = sum(1 for _, m in to_convert if m == 'transcode')
    logger.info(f"Found {len(to_convert)} incompatible video(s): "
                f"{remux_count} remux (fast), {transcode_count} transcode (slow)")
    logger.info("Waiting for user confirmation to convert...")

    # Build file list for the frontend dialog
    file_list = []
    for fp, mode in to_convert:
        file_list.append({
            'name': fp.name,
            'size_mb': round(fp.stat().st_size / 1024 / 1024, 1),
            'mode': mode,
        })

    _conversion_state['phase'] = 'waiting'
    _conversion_state['total'] = len(to_convert)
    _conversion_state['files'] = file_list


def run_conversion() -> None:
    """Run the actual conversion of all incompatible videos.
    Called from /api/convert endpoint in a background thread.
    """
    global _to_convert
    if not _to_convert:
        return

    _conversion_state['phase'] = 'converting'
    _conversion_state['total'] = len(_to_convert)
    _conversion_state['done_count'] = 0
    _conversion_state['failed_count'] = 0
    _conversion_state['percent'] = 0

    # Check NVENC availability once (only if there are videos to transcode)
    has_nvenc = False
    transcode_count = sum(1 for _, m in _to_convert if m == 'transcode')
    if transcode_count > 0:
        has_nvenc = _check_nvenc_available()
        if has_nvenc:
            logger.info("NVIDIA NVENC hardware encoder available.")
        else:
            logger.info("Using software encoder (x264).")

    success = 0
    failed = 0
    for i, (file_path, mode) in enumerate(_to_convert, 1):
        _conversion_state['current_index'] = i
        _conversion_state['current_file'] = file_path.name
        _conversion_state['percent'] = 0
        size_mb = file_path.stat().st_size / 1024 / 1024
        logger.info(f"[{i}/{len(_to_convert)}] {mode.upper()} ({size_mb:.1f} MB): {file_path.name}")
        if _convert_single_video(file_path, mode, has_nvenc):
            success += 1
            _conversion_state['done_count'] = success
        else:
            failed += 1
            _conversion_state['failed_count'] = failed

    _conversion_state['phase'] = 'done'
    _to_convert = []
    logger.info(f"Conversion complete: {success} OK, {failed} failed")


def _convert_single_video(file_path: Path, mode: str, has_nvenc: bool) -> bool:
    """Convert a single video file in-place.
    Returns True on success, False on failure (original is preserved).
    """
    # Use a short temp name to avoid Windows MAX_PATH (260 char) limit
    temp_path = file_path.parent / f'_converting_{os.getpid()}.mp4'
    duration = _get_duration_seconds(file_path)

    try:
        if mode == 'remux':
            # Fast: copy streams into MP4 container
            cmd = [
                'ffmpeg', '-y', '-i', str(file_path),
                '-c', 'copy',
                '-movflags', '+faststart',
                str(temp_path)
            ]
            print(f'\r  {_progress_bar(0)}   0% Remuxing (stream copy)...', end='', flush=True)
            rc, stderr = _run_ffmpeg_with_progress(cmd, duration, 'Remuxing')

            if rc != 0:
                logger.warning(f"  Remux failed, trying full transcode...")
                if temp_path.exists():
                    temp_path.unlink()
                mode = 'transcode'

        if mode == 'transcode':
            encoder_label = 'NVENC' if has_nvenc else 'x264'
            if has_nvenc:
                encode_args = [
                    '-c:v', 'h264_nvenc', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                    '-preset', 'p4', '-rc', 'vbr', '-cq', '20',
                ]
            else:
                encode_args = [
                    '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                    '-preset', 'veryfast', '-crf', '20',
                ]

            cmd = (
                ['ffmpeg', '-y', '-i', str(file_path)]
                + encode_args
                + ['-c:a', 'aac', '-b:a', '128k',
                   '-movflags', '+faststart',
                   str(temp_path)]
            )
            dur_str = f"{int(duration // 60)}m{int(duration % 60)}s" if duration > 0 else "?"
            print(f'\r  {_progress_bar(0)}   0% Transcoding {encoder_label} ({dur_str})...', end='', flush=True)
            rc, stderr = _run_ffmpeg_with_progress(cmd, duration, f'Transcoding ({encoder_label})')

            # If NVENC failed, retry with software
            if rc != 0 and has_nvenc:
                logger.info(f"  NVENC failed, retrying with x264...")
                if temp_path.exists():
                    temp_path.unlink()
                cmd_sw = [
                    'ffmpeg', '-y', '-i', str(file_path),
                    '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                    '-preset', 'veryfast', '-crf', '20',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-movflags', '+faststart',
                    str(temp_path)
                ]
                rc, stderr = _run_ffmpeg_with_progress(cmd, duration, 'Transcoding (x264)')

            if rc != 0:
                logger.error(f"  FAILED: {stderr[:300]}")
                if temp_path.exists():
                    temp_path.unlink()
                return False

        # Verify the converted file before replacing
        print(f'\r  {_progress_bar(100)} Verifying output...                    ', end='', flush=True)
        if not _verify_converted(file_path, temp_path):
            logger.error(f"  Verification FAILED - keeping original: {file_path.name}")
            if temp_path.exists():
                temp_path.unlink()
            return False

        # Replace original with converted file
        original_size = file_path.stat().st_size
        converted_size = temp_path.stat().st_size

        # Delete original and rename temp
        file_path.unlink()
        temp_path.rename(file_path)

        print(f'\r  {_progress_bar(100)} Done ({original_size / 1024 / 1024:.1f} MB -> {converted_size / 1024 / 1024:.1f} MB)          ', flush=True)
        return True

    except Exception as e:
        logger.exception(f"  Error converting {file_path.name}: {e}")
        # Clean up temp file, keep original
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return False


class RangeHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with Range request support for video seeking."""

    # Larger buffer for faster streaming (1MB instead of default 8KB)
    rbufsize = 1024 * 1024
    wbufsize = 1024 * 1024

    def send_head(self):
        if 'Range' not in self.headers:
            self.range = None
            return super().send_head()

        try:
            self.range = re.search(r'bytes=(\d+)-(\d*)', self.headers['Range'])
        except ValueError:
            self.range = None
            return super().send_head()

        if not self.range:
            return super().send_head()

        path = self.translate_path(self.path)
        f = None
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        try:
            fs = os.fstat(f.fileno())
            file_len = fs[6]
        except:
            f.close()
            return None

        start, end = self.range.groups()
        start = int(start)
        if end:
            end = int(end)
        else:
            end = file_len - 1

        if start >= file_len:
            self.send_error(416, "Requested Range Not Satisfiable")
            self.send_header("Content-Range", f"bytes */{file_len}")
            self.end_headers()
            f.close()
            return None

        self.send_response(206)
        self.send_header("Content-type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_len}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Connection", "keep-alive")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()

        f.seek(start)
        return LimitedFileWrapper(f, end - start + 1)


class LimitedFileWrapper:
    """Wrapper to limit file reads for Range requests."""

    # 2MB chunks for faster streaming
    CHUNK_SIZE = 2 * 1024 * 1024

    def __init__(self, f, length):
        self.f = f
        self.length = length
        self.read_so_far = 0

    def read(self, size=-1):
        if self.read_so_far >= self.length:
            return b""
        if size < 0:
            # Read in chunks to avoid memory issues with large files
            size = self.CHUNK_SIZE
        remaining = self.length - self.read_so_far
        to_read = min(size, remaining, self.CHUNK_SIZE)
        data = self.f.read(to_read)
        self.read_so_far += len(data)
        return data

    def close(self):
        self.f.close()


class VideoPlayerHandler(RangeHTTPRequestHandler):
    """Main request handler for the video player server."""

    # Class variables set by main()
    course_path = None
    port = None

    def __init__(self, *args, **kwargs):
        # Set directory to course path for media serving
        super().__init__(*args, directory=str(self.course_path), **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        path = unquote(self.path)

        # API endpoints
        if path == '/api/playlist':
            self.handle_playlist()
            return

        if path == '/api/conversion-status':
            self.send_json(_conversion_state)
            return

        # Serve index.html for root
        if path == '/' or path == '/index.html':
            self.serve_static_file('web/index.html', 'text/html')
            return

        # Serve static files (CSS, JS, favicon)
        if path.startswith('/static/'):
            static_path = path[8:]  # Remove '/static/'
            if static_path.endswith('.css'):
                self.serve_static_file(f'web/css/{static_path}', 'text/css')
            elif static_path.endswith('.js'):
                self.serve_static_file(f'web/js/{static_path}', 'application/javascript')
            elif static_path.endswith('.svg'):
                self.serve_static_file(f'web/static/{static_path}', 'image/svg+xml')
            elif static_path.endswith('.ico'):
                self.serve_static_file(f'web/static/{static_path}', 'image/x-icon')
            else:
                logger.warning(f"Unknown static file type: {static_path}")
                self.send_error(404, "Static file not found")
            return

        # Serve media files from course directory
        if path.startswith('/media/'):
            media_path = path[7:]  # Remove '/media/'
            self.serve_media_file(media_path)
            return

        # Default: 404
        self.send_error(404, "Not found")

    def do_POST(self):
        """Handle POST requests."""
        path = unquote(self.path)

        if path == '/api/duration':
            self.handle_duration_request()
            return

        if path == '/api/open-folder':
            self.handle_open_folder()
            return

        if path == '/api/convert':
            self.handle_start_conversion()
            return

        self.send_error(404, "Not found")

    def handle_open_folder(self):
        """Open the folder containing a file and select it."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            file_path = data.get('path')
            if not file_path:
                self.send_error(400, "Missing 'path' parameter")
                return

            # Convert media path to actual file path
            if file_path.startswith('/media/'):
                relative = file_path[7:]  # Remove '/media/'
                actual_path = self.course_path / unquote(relative)
            else:
                actual_path = self.course_path / unquote(file_path)

            actual_path = actual_path.resolve()

            # Security check
            if not str(actual_path).startswith(str(self.course_path.resolve())):
                self.send_error(403, "Access denied")
                return

            if not actual_path.exists():
                # Try parent folder if file doesn't exist
                actual_path = actual_path.parent

            if actual_path.exists():
                import subprocess
                import platform

                if platform.system() == 'Windows':
                    if actual_path.is_file():
                        # Open folder and select the file
                        subprocess.run(['explorer', '/select,', str(actual_path)], check=False)
                    else:
                        # Just open the folder
                        subprocess.run(['explorer', str(actual_path)], check=False)
                elif platform.system() == 'Darwin':  # macOS
                    if actual_path.is_file():
                        subprocess.run(['open', '-R', str(actual_path)], check=False)
                    else:
                        subprocess.run(['open', str(actual_path)], check=False)
                else:  # Linux
                    folder = actual_path.parent if actual_path.is_file() else actual_path
                    subprocess.run(['xdg-open', str(folder)], check=False)

                self.send_json({'success': True})
            else:
                self.send_error(404, "Path not found")

        except Exception as e:
            logger.exception(f"Error opening folder: {e}")
            self.send_error(500, str(e))

    def handle_start_conversion(self):
        """Start converting incompatible videos (triggered by user from frontend dialog)."""
        if _conversion_state['phase'] != 'waiting':
            self.send_json({'success': False, 'error': 'Not in waiting state'})
            return

        # Start conversion in a background thread
        t = threading.Thread(target=run_conversion, daemon=True)
        t.start()
        self.send_json({'success': True})

    def handle_duration_request(self):
        """Calculate duration for a single video (called one at a time from frontend)."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            video_path = data.get('path')
            if not video_path:
                self.send_error(400, "Missing 'path' parameter")
                return

            result = calculate_duration_for_video(self.course_path, video_path)
            self.send_json(result)

        except Exception as e:
            logger.exception(f"Error calculating duration: {e}")
            self.send_error(500, str(e))

    def handle_playlist(self):
        """Generate and return the playlist JSON."""
        try:
            playlist = scan_directory(self.course_path, self.port)
            self.send_json(playlist)
        except Exception as e:
            logger.exception(f"Error generating playlist: {e}")
            self.send_error(500, str(e))

    def serve_static_file(self, relative_path, content_type):
        """Serve a static file from the script directory."""
        file_path = SCRIPT_DIR / relative_path
        if not file_path.exists():
            logger.warning(f"Static file not found: {relative_path}")
            self.send_error(404, f"File not found: {relative_path}")
            return

        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            # No cache for development - easier to see changes
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.exception(f"Error serving static file {relative_path}: {e}")
            self.send_error(500, str(e))

    def serve_media_file(self, relative_path):
        """Serve a media file from the course directory."""
        # Decode URL-encoded path
        decoded_path = unquote(relative_path)
        file_path = self.course_path / decoded_path

        # Security check: prevent directory traversal
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(self.course_path.resolve())):
                self.send_error(403, "Access denied")
                return
        except:
            self.send_error(400, "Invalid path")
            return

        if not file_path.exists():
            logger.warning(f"Media not found: {decoded_path}")
            self.send_error(404, f"Media not found: {decoded_path}")
            return

        if not file_path.is_file():
            self.send_error(400, "Not a file")
            return

        serve_path = file_path

        # Serve file directly (bypass SimpleHTTPRequestHandler.translate_path
        # which can fail with special characters on Windows)
        try:
            file_size = serve_path.stat().st_size
            ctype = mimetypes.guess_type(str(serve_path))[0] or 'application/octet-stream'

            # Handle Range requests for video seeking
            range_header = self.headers.get('Range')
            if range_header:
                range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

                    if start >= file_size:
                        self.send_error(416, "Requested Range Not Satisfiable")
                        return

                    end = min(end, file_size - 1)

                    self.send_response(206)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "public, max-age=3600")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()

                    with open(serve_path, 'rb') as f:
                        f.seek(start)
                        remaining = end - start + 1
                        chunk_size = 2 * 1024 * 1024  # 2MB chunks
                        while remaining > 0:
                            to_read = min(chunk_size, remaining)
                            data = f.read(to_read)
                            if not data:
                                break
                            self.wfile.write(data)
                            remaining -= len(data)
                    return

            # Full file response
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Last-Modified",
                             self.date_time_string(serve_path.stat().st_mtime))
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            with open(serve_path, 'rb') as f:
                chunk_size = 2 * 1024 * 1024  # 2MB chunks
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    self.wfile.write(data)

        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.exception(f"Error serving media file {decoded_path}: {e}")
            self.send_error(500, str(e))

    def send_json(self, data):
        """Send JSON response."""
        content = json.dumps(data, cls=NodeEncoder, ensure_ascii=False, indent=2)
        encoded = content.encode('utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(encoded))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        """Custom logging."""
        if '/api/' in args[0] or args[0].startswith('"GET / '):
            logger.debug(args[0])


class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threaded HTTP server for handling multiple connections."""
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        """Bind with optimized socket settings."""
        import socket
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Disable Nagle's algorithm for lower latency
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        super().server_bind()

    def handle_error(self, request, client_address):
        """Suppress connection reset errors."""
        pass


def find_free_port(start_port, max_port):
    """Find an available port in the given range."""
    import socket
    for port in range(start_port, max_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description='Video Player Server')
    parser.add_argument('--port', type=int, default=0,
                        help=f'Port to use (0 = auto-detect free port, default: {DEFAULT_PORT}-{MAX_PORT})')
    parser.add_argument('--path', type=str, required=True,
                        help='Path to the course directory')

    args = parser.parse_args()

    # Validate course path
    course_path = Path(args.path).resolve()
    if not course_path.exists():
        logger.error(f"Path does not exist: {course_path}")
        sys.exit(1)
    if not course_path.is_dir():
        logger.error(f"Path is not a directory: {course_path}")
        sys.exit(1)

    # Find port
    if args.port == 0:
        port = find_free_port(DEFAULT_PORT, MAX_PORT)
        if port is None:
            logger.error(f"No free port found in range {DEFAULT_PORT}-{MAX_PORT}")
            sys.exit(1)
    else:
        port = args.port

    # Set handler class variables
    VideoPlayerHandler.course_path = course_path
    VideoPlayerHandler.port = port

    # Get local IP for LAN access
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    # Start server
    logger.info("=" * 50)
    logger.info("  VIDEO PLAYER SERVER")
    logger.info("=" * 50)
    logger.info(f"  Port:   {port}")
    logger.info(f"  Course: {course_path}")
    logger.info(f"  Local:  http://localhost:{port}")
    logger.info(f"  LAN:    http://{local_ip}:{port}")
    logger.info("=" * 50)

    # Scan for incompatible videos in background thread (server starts immediately)
    scan_thread = threading.Thread(
        target=scan_videos_on_startup,
        args=(course_path,),
        daemon=True
    )
    scan_thread.start()

    try:
        with ThreadedHTTPServer(("", port), VideoPlayerHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
