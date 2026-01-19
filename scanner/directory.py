"""
Directory scanner for building the playlist structure.

Recursively scans a directory and builds a Course object containing:
- Chapters (folders)
- Videos (mp4, mkv, webm)
- Documents (pdf, txt, json, zip, images)
- Subtitles (srt, vtt) - linked to matching videos

Duration calculation is deferred to avoid slow startup.
"""

import os
import re
import subprocess
import json
import hashlib
import unicodedata
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

from .model import Course, Chapter, Video, Document, Subtitle, DocumentType
from .ordering import sort_items, extract_sort_key, get_clean_title


# File extensions
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.avi', '.mov', '.m4v'}
SUBTITLE_EXTENSIONS = {'.srt', '.vtt'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
DOCUMENT_EXTENSIONS = {'.pdf', '.txt', '.json', '.zip', '.rar', '.7z', '.md', '.html', '.htm', '.docx'}

# Folders to ignore
IGNORE_FOLDERS = {'.git', '__pycache__', 'node_modules', '.vscode', 'trash', 'deleteVideos', '.idea'}


def get_document_type(extension: str) -> DocumentType:
    """Determine document type from file extension."""
    ext = extension.lower()
    if ext == '.pdf':
        return DocumentType.PDF
    elif ext in IMAGE_EXTENSIONS:
        return DocumentType.IMAGE
    elif ext == '.txt' or ext == '.md':
        return DocumentType.TEXT
    elif ext == '.json':
        return DocumentType.JSON
    elif ext in {'.zip', '.rar', '.7z'}:
        return DocumentType.ZIP
    elif ext in {'.html', '.htm'}:
        return DocumentType.HTML
    elif ext == '.docx':
        return DocumentType.DOCX
    else:
        return DocumentType.OTHER


def get_video_duration(file_path: Path) -> int:
    """
    Get video duration in seconds using ffprobe.
    Returns 0 if ffprobe is not available or fails.
    """
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                str(file_path)
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data.get('format', {}).get('duration', 0))
            return int(duration)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, KeyError, OSError):
        pass
    except Exception:
        pass
    return 0


def generate_structure_hash(root_path: Path) -> str:
    """
    Generate a hash of the directory structure.
    Used to detect if files/folders have changed.
    Includes: file names, sizes, modification times.
    """
    hash_data = []

    for root, dirs, files in os.walk(root_path):
        # Filter ignored directories
        dirs[:] = sorted([d for d in dirs if d not in IGNORE_FOLDERS and not d.startswith('.')])

        rel_root = os.path.relpath(root, root_path)

        for f in sorted(files):
            if f.startswith('.'):
                continue
            file_path = Path(root) / f
            try:
                stat = file_path.stat()
                # Include: relative path, size, mtime
                hash_data.append(f"{rel_root}/{f}|{stat.st_size}|{int(stat.st_mtime)}")
            except:
                pass

    content = "\n".join(hash_data)
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def find_subtitles(video_path: Path, all_files: List[Path]) -> List[Subtitle]:
    """
    Find subtitle files matching a video.

    Matching rules (in order of priority):
    1. Exact name match: video.mp4 -> video.srt, video.en.srt
    2. Flexible: If only one video in folder, link ALL subtitle files in that folder
    """
    video_stem = video_path.stem.lower()
    video_dir = video_path.parent
    subtitles = []

    lang_codes = {
        'en': 'English', 'eng': 'English', 'english': 'English',
        'es': 'Spanish', 'spa': 'Spanish', 'spanish': 'Spanish',
        'fr': 'French', 'fra': 'French', 'french': 'French',
        'de': 'German', 'deu': 'German', 'german': 'German',
        'it': 'Italian', 'ita': 'Italian', 'italian': 'Italian',
        'pt': 'Portuguese', 'por': 'Portuguese', 'portuguese': 'Portuguese',
        'ru': 'Russian', 'rus': 'Russian', 'russian': 'Russian',
        'zh': 'Chinese', 'chi': 'Chinese', 'chinese': 'Chinese',
        'ja': 'Japanese', 'jpn': 'Japanese', 'japanese': 'Japanese',
        'ko': 'Korean', 'kor': 'Korean', 'korean': 'Korean',
    }

    # Get all subtitle files in the same directory
    dir_subtitles = [f for f in all_files
                     if f.suffix.lower() in SUBTITLE_EXTENSIONS and f.parent == video_dir]

    # Count videos in the same directory
    dir_videos = [f for f in all_files
                  if f.suffix.lower() in VIDEO_EXTENSIONS and f.parent == video_dir]

    # If only one video in folder, link ALL subtitles in that folder
    is_single_video_folder = len(dir_videos) == 1

    for file_path in dir_subtitles:
        sub_stem = file_path.stem.lower()

        # Check if subtitle matches video name
        name_matches = sub_stem.startswith(video_stem)

        # Skip if name doesn't match AND there are multiple videos in folder
        if not name_matches and not is_single_video_folder:
            continue

        # Try to extract language from filename
        lang = 'en'
        label = 'English'

        # Check for language code in filename
        if name_matches:
            remainder = sub_stem[len(video_stem):]
        else:
            # Use whole filename for language detection
            remainder = sub_stem

        if remainder:
            remainder = remainder.lstrip('._- ')
            for code, name in lang_codes.items():
                if remainder == code or remainder.startswith(code + '.') or code in remainder.lower():
                    lang = code[:2] if len(code) > 2 else code
                    label = name
                    break
            else:
                # No known language code found
                if remainder and not name_matches:
                    # Use subtitle filename as label if it doesn't match video
                    label = file_path.stem
                elif remainder:
                    lang = remainder[:2]
                    label = remainder.capitalize()

        subtitles.append(Subtitle(
            lang=lang,
            label=label,
            file=file_path.name,
            path=""
        ))

    return subtitles


def build_url_path(file_path: Path, root_path: Path) -> str:
    """Build URL path for a file relative to the course root."""
    relative = file_path.relative_to(root_path)
    parts = [quote(part, safe='') for part in relative.parts]
    return '/media/' + '/'.join(parts)


def scan_folder(
    folder_path: Path,
    root_path: Path,
    all_files: List[Path],
    depth: int = 0
) -> Tuple[List[Video], List[Document], List[Chapter]]:
    """
    Scan a single folder and return its contents.
    Duration is set to 0 - will be calculated later via API.
    """
    videos = []
    documents = []
    sub_chapters = []

    try:
        # Use os.scandir with long path support for Windows
        scan_path = _to_long_path(str(folder_path.resolve()))
        items = []
        files = []
        folders = []

        with os.scandir(scan_path) as entries:
            for entry in entries:
                if entry.name.startswith('.'):
                    continue
                # Build path without \\?\ prefix
                item_path = Path(folder_path) / entry.name

                if entry.is_file(follow_symlinks=False):
                    files.append(item_path)
                elif entry.is_dir(follow_symlinks=False):
                    if entry.name not in IGNORE_FOLDERS:
                        folders.append(item_path)
    except (PermissionError, OSError):
        return [], [], []

    # Helper to get creation time (for items starting with "-")
    def get_ctime(path):
        try:
            return path.stat().st_ctime
        except:
            return 0

    files = sort_items(files, key_func=lambda f: f.name, ctime_func=get_ctime)
    folders = sort_items(folders, key_func=lambda f: f.name, ctime_func=get_ctime)

    order = 1
    for file_path in files:
        ext = file_path.suffix.lower()

        if ext in VIDEO_EXTENSIONS:
            subtitles = find_subtitles(file_path, all_files)
            for sub in subtitles:
                sub_file = file_path.parent / sub.file
                sub.path = build_url_path(sub_file, root_path)

            video = Video(
                title=get_clean_title(file_path.name),
                file=file_path.name,
                path=build_url_path(file_path, root_path),
                order=order,
                duration=0,  # Calculated later
                subtitles=subtitles
            )
            videos.append(video)
            order += 1

        elif ext in SUBTITLE_EXTENSIONS:
            pass

        elif ext in IMAGE_EXTENSIONS or ext in DOCUMENT_EXTENSIONS:
            doc = Document(
                type=get_document_type(ext),
                title=file_path.name,
                file=file_path.name,
                path=build_url_path(file_path, root_path)
            )
            documents.append(doc)

    for folder in folders:
        sub_videos, sub_docs, sub_sub_chapters = scan_folder(
            folder, root_path, all_files, depth + 1
        )

        # Check if this folder has any videos (directly or in children)
        def has_videos_recursive(vids, chapters):
            if vids:
                return True
            for ch in chapters:
                if has_videos_recursive(ch.videos, ch.children):
                    return True
            return False

        has_videos = has_videos_recursive(sub_videos, sub_sub_chapters)

        # Check if this is a "wrapper" folder: contains only 1 video and no child chapters
        # These folders exist just to keep video + subtitles organized together
        # Flatten them by promoting the video to the parent level
        is_wrapper_folder = (
            len(sub_videos) == 1 and
            len(sub_sub_chapters) == 0
        )

        if is_wrapper_folder:
            # Promote the single video to parent level
            # The video already has its subtitles linked
            # Use the folder's sort key for ordering so "0. Intro" folder sorts before "1. Basics"
            # Also use the folder name as the video title (preserving numbering like "0. Introducción")
            _, folder_sort_num, _ = extract_sort_key(folder.name)
            for vid in sub_videos:
                vid.order = folder_sort_num
                vid.title = folder.name  # Use folder name as title to preserve numbering
            videos.extend(sub_videos)
            # Also promote any documents
            documents.extend(sub_docs)
        elif has_videos:
            # Normal chapter with videos
            # Use full folder name to preserve numbering (e.g., "1. Generación de la Idea")
            # Extract order from folder name for proper sorting
            _, folder_sort_num, _ = extract_sort_key(folder.name)
            chapter = Chapter(
                title=folder.name,
                order=folder_sort_num,
                path=str(folder.relative_to(root_path)),
                videos=sub_videos,
                documents=sub_docs,
                children=sub_sub_chapters
            )
            sub_chapters.append(chapter)
        elif sub_docs or sub_sub_chapters:
            # Folder has documents but no videos - still show as chapter
            # Extract order from folder name for proper sorting
            _, folder_sort_num, _ = extract_sort_key(folder.name)
            chapter = Chapter(
                title=folder.name,
                order=folder_sort_num,
                path=str(folder.relative_to(root_path)),
                videos=[],
                documents=sub_docs,
                children=sub_sub_chapters
            )
            sub_chapters.append(chapter)

    # Sort videos by order (important when videos are promoted from wrapper folders)
    videos = sort_items(videos, key_func=lambda v: v.title)
    # Sort chapters using full sort key (prefix + number) to keep groups together
    sub_chapters = sort_items(sub_chapters, key_func=lambda c: c.title)
    return videos, documents, sub_chapters


def _to_long_path(path_str: str) -> str:
    """Convert path string to Windows long path format.

    Windows has a 260 character path limit. Using \\?\ prefix bypasses this.
    """
    if os.name == 'nt' and not path_str.startswith('\\\\?\\'):
        # Convert forward slashes and make absolute
        path_str = os.path.abspath(path_str)
        return '\\\\?\\' + path_str
    return path_str


def get_all_files(root_path: Path) -> List[Path]:
    """Get all files in the directory tree.

    Handles Windows long paths (>260 chars) by using \\?\ prefix.
    """
    all_files = []
    root_str = str(root_path.resolve())

    def scan_dir(dir_path: str):
        try:
            # Use long path format on Windows for scanning
            scan_path = _to_long_path(dir_path)

            with os.scandir(scan_path) as entries:
                for entry in entries:
                    name = entry.name
                    if name.startswith('.'):
                        continue
                    if name in IGNORE_FOLDERS:
                        continue

                    # Build the normal path (without \\?\ prefix)
                    item_path = os.path.join(dir_path, name)

                    if entry.is_dir(follow_symlinks=False):
                        scan_dir(item_path)
                    elif entry.is_file(follow_symlinks=False):
                        all_files.append(Path(item_path))
        except PermissionError:
            pass
        except OSError:
            pass

    scan_dir(root_str)
    return all_files


def scan_directory(root_path: Path, port: int) -> dict:
    """
    Scan a directory and build the complete course structure.
    Duration is NOT calculated here - use get_video_durations() separately.
    """
    root_path = Path(root_path).resolve()

    # Generate structure hash for cache validation
    structure_hash = generate_structure_hash(root_path)

    all_files = get_all_files(root_path)

    root_videos, root_docs, chapters = scan_folder(
        root_path, root_path, all_files, depth=0
    )

    course = Course(
        title=root_path.name,
        root_path=str(root_path),
        port=port,
        chapters=chapters,
        documents=root_docs,
        videos=root_videos
    )

    result = course.to_dict()
    result['structure_hash'] = structure_hash

    return result


def get_all_video_paths(data: dict) -> List[str]:
    """Extract all video paths from playlist data."""
    paths = []

    # Root videos
    for v in data.get('videos', []):
        paths.append(v['path'])

    # Chapter videos (recursive)
    def process_chapter(chapter):
        for v in chapter.get('videos', []):
            paths.append(v['path'])
        for child in chapter.get('children', []):
            process_chapter(child)

    for ch in data.get('chapters', []):
        process_chapter(ch)

    return paths


def calculate_duration_for_video(root_path: Path, video_path: str) -> dict:
    """
    Calculate duration for a single video.
    Returns: { "path": ..., "duration": seconds }
    """
    # Convert URL path to file path
    # video_path is like "/media/Chapter/video.mp4"
    relative = video_path.replace('/media/', '', 1)
    from urllib.parse import unquote
    relative = unquote(relative)
    file_path = root_path / relative

    duration = get_video_duration(file_path)

    return {
        "path": video_path,
        "duration": duration
    }


# Test
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        result = scan_directory(path, 8002)
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python -m scanner.directory <path>")
