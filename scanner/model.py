"""
Data models for the video player playlist structure.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import json


class NodeType(Enum):
    """Type of node in the playlist tree."""
    COURSE = "course"
    CHAPTER = "chapter"
    VIDEO = "video"
    DOCUMENT = "document"
    SUBTITLE = "subtitle"


class DocumentType(Enum):
    """Supported document types."""
    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    JSON = "json"
    ZIP = "zip"
    HTML = "html"
    OTHER = "other"


@dataclass
class Subtitle:
    """Subtitle track for a video."""
    lang: str
    label: str
    path: str
    file: str


@dataclass
class Document:
    """Document attached to a chapter or video."""
    type: DocumentType
    title: str
    file: str
    path: str

    def to_dict(self):
        return {
            "type": self.type.value,
            "title": self.title,
            "file": self.file,
            "path": self.path
        }


@dataclass
class Video:
    """A video lesson."""
    title: str
    file: str
    path: str
    order: int
    duration: int = 0  # seconds
    subtitles: List[Subtitle] = field(default_factory=list)

    def to_dict(self):
        return {
            "type": "video",
            "title": self.title,
            "file": self.file,
            "path": self.path,
            "order": self.order,
            "duration": self.duration,
            "subtitles": [
                {
                    "lang": s.lang,
                    "label": s.label,
                    "path": s.path,
                    "file": s.file
                } for s in self.subtitles
            ]
        }


@dataclass
class Chapter:
    """A chapter/folder containing videos and documents."""
    title: str
    order: int
    path: str
    videos: List[Video] = field(default_factory=list)
    documents: List[Document] = field(default_factory=list)
    children: List['Chapter'] = field(default_factory=list)  # Sub-chapters

    @property
    def duration(self) -> int:
        """Total duration of all videos in this chapter."""
        total = sum(v.duration for v in self.videos)
        for child in self.children:
            total += child.duration
        return total

    @property
    def video_count(self) -> int:
        """Total number of videos in this chapter."""
        count = len(self.videos)
        for child in self.children:
            count += child.video_count
        return count

    def to_dict(self):
        return {
            "type": "chapter",
            "title": self.title,
            "order": self.order,
            "path": self.path,
            "duration": self.duration,
            "video_count": self.video_count,
            "videos": [v.to_dict() for v in self.videos],
            "documents": [d.to_dict() for d in self.documents],
            "children": [c.to_dict() for c in self.children]
        }


@dataclass
class Course:
    """Root course structure."""
    title: str
    root_path: str
    port: int
    chapters: List[Chapter] = field(default_factory=list)
    documents: List[Document] = field(default_factory=list)  # Root-level docs
    videos: List[Video] = field(default_factory=list)  # Root-level videos

    @property
    def total_duration(self) -> int:
        """Total duration of all videos in the course."""
        total = sum(v.duration for v in self.videos)
        for chapter in self.chapters:
            total += chapter.duration
        return total

    @property
    def total_videos(self) -> int:
        """Total number of videos in the course."""
        count = len(self.videos)
        for chapter in self.chapters:
            count += chapter.video_count
        return count

    def to_dict(self):
        return {
            "type": "course",
            "title": self.title,
            "root_path": self.root_path,
            "port": self.port,
            "total_duration": self.total_duration,
            "total_videos": self.total_videos,
            "chapters": [c.to_dict() for c in self.chapters],
            "documents": [d.to_dict() for d in self.documents],
            "videos": [v.to_dict() for v in self.videos]
        }


class NodeEncoder(json.JSONEncoder):
    """JSON encoder for playlist nodes."""

    def default(self, obj):
        if isinstance(obj, (Course, Chapter, Video, Document)):
            return obj.to_dict()
        if isinstance(obj, Subtitle):
            return {
                "lang": obj.lang,
                "label": obj.label,
                "path": obj.path,
                "file": obj.file
            }
        if isinstance(obj, (NodeType, DocumentType)):
            return obj.value
        return super().default(obj)
