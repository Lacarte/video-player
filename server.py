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
from pathlib import Path
from urllib.parse import unquote, quote

# Add scanner module to path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from scanner.directory import scan_directory, calculate_duration_for_video
from scanner.model import NodeEncoder

# Configuration
DEFAULT_PORT = 8002
MAX_PORT = 8020

# MIME types
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('video/x-matroska', '.mkv')
mimetypes.add_type('text/vtt', '.vtt')
mimetypes.add_type('application/x-subrip', '.srt')


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

        # Serve index.html for root
        if path == '/' or path == '/index.html':
            self.serve_static_file('web/index.html', 'text/html')
            return

        # Serve static files (CSS, JS)
        if path.startswith('/static/'):
            static_path = path[8:]  # Remove '/static/'
            if static_path.endswith('.css'):
                self.serve_static_file(f'web/css/{static_path}', 'text/css')
            elif static_path.endswith('.js'):
                self.serve_static_file(f'web/js/{static_path}', 'application/javascript')
            else:
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

        self.send_error(404, "Not found")

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
            print(f"Error calculating duration: {e}")
            self.send_error(500, str(e))

    def handle_playlist(self):
        """Generate and return the playlist JSON."""
        try:
            playlist = scan_directory(self.course_path, self.port)
            self.send_json(playlist)
        except Exception as e:
            print(f"Error generating playlist: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, str(e))

    def serve_static_file(self, relative_path, content_type):
        """Serve a static file from the script directory."""
        file_path = SCRIPT_DIR / relative_path
        if not file_path.exists():
            self.send_error(404, f"File not found: {relative_path}")
            return

        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            # Cache static files for 1 hour during development, use no-cache for HTML
            if content_type == 'text/html':
                self.send_header('Cache-Control', 'no-cache')
            else:
                self.send_header('Cache-Control', 'public, max-age=3600')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
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
            self.send_error(404, f"Media not found: {decoded_path}")
            return

        if not file_path.is_file():
            self.send_error(400, "Not a file")
            return

        # Update path for parent class handler
        self.path = '/' + str(file_path.relative_to(self.course_path)).replace('\\', '/')

        try:
            super().do_GET()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

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
            print(f"[{self.log_date_time_string()}] {args[0]}")


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
        print(f"Error: Path does not exist: {course_path}")
        sys.exit(1)
    if not course_path.is_dir():
        print(f"Error: Path is not a directory: {course_path}")
        sys.exit(1)

    # Find port
    if args.port == 0:
        port = find_free_port(DEFAULT_PORT, MAX_PORT)
        if port is None:
            print(f"Error: No free port found in range {DEFAULT_PORT}-{MAX_PORT}")
            sys.exit(1)
    else:
        port = args.port

    # Set handler class variables
    VideoPlayerHandler.course_path = course_path
    VideoPlayerHandler.port = port

    # Start server
    print()
    print("=" * 50)
    print("  VIDEO PLAYER SERVER")
    print("=" * 50)
    print(f"  Port:   {port}")
    print(f"  Course: {course_path}")
    print(f"  URL:    http://localhost:{port}")
    print("=" * 50)
    print()

    try:
        with ThreadedHTTPServer(("", port), VideoPlayerHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
