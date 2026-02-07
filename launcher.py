#!/usr/bin/env python3
"""
Video Player Launcher
Handles paths with special characters (!, ~, etc.) that break batch scripts.
"""
import sys
import os
import socket
import subprocess
import webbrowser
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_PORT = 8002
MAX_PORT = 8020

def find_free_port():
    """Find an available port."""
    for port in range(BASE_PORT, MAX_PORT + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return None

def main():
    # Get target directory
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = os.getcwd()

    # Verify path exists
    target_path = Path(target_dir)
    if not target_path.exists():
        print(f"ERROR: Path does not exist: {target_dir}")
        input("Press Enter to exit...")
        sys.exit(1)

    # Find available port
    port = find_free_port()
    if not port:
        print(f"ERROR: No free port found in range {BASE_PORT}-{MAX_PORT}")
        input("Press Enter to exit...")
        sys.exit(1)

    # Open browser
    webbrowser.open(f"http://localhost:{port}")

    # Find Python executable
    venv_python = SCRIPT_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        python_exe = str(venv_python)
    else:
        python_exe = sys.executable

    # Run server
    server_py = SCRIPT_DIR / "server.py"

    print()
    print("=" * 50)
    print("  VIDEO PLAYER")
    print("=" * 50)
    print(f"  Port:   {port}")
    print(f"  Course: {target_dir}")
    print(f"  URL:    http://localhost:{port}")
    print("=" * 50)
    print()
    print("Press Ctrl+C to stop the server.")
    print()

    try:
        subprocess.run([
            python_exe,
            str(server_py),
            "--port", str(port),
            "--path", target_dir
        ])
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
