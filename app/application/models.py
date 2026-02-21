from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ScanProgress:
    phase: str
    message: str
    current: int = 0
    total: int = 0
    indeterminate: bool = False
    rel_path: str = ""


@dataclass(frozen=True)
class TagMiningProgress:
    phase: str
    message: str
    current: int = 0
    total: int = 0
    indeterminate: bool = False
    rel_path: str = ""


@dataclass(frozen=True)
class TagMiningResult:
    processed_videos: int
    selected_terms: int
    tagged_videos: int
    created_relations: int
    elapsed_ms: int
    status: str = "completed"
    strategy_requested: str = "auto"
    strategy_used: str = "rule"
    model_name: str = ""
    reranker_name: str = ""
    fallback_reason: str = ""
    scope: str = "all"
    threshold_config_path: str = ""
    pending_candidate_terms: int = 0
    pending_candidate_hits: int = 0
    semantic_auto_hits: int = 0
    semantic_pending_hits: int = 0
    semantic_rejected_hits: int = 0
    top_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScanResult:
    added: int
    updated: int
    seen: int
    refresh_rel_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScannedFile:
    rel_path: str
    filename: str
    ext: str
    size_bytes: int
    mtime_epoch: int


@dataclass(frozen=True)
class MediaRecord:
    rel_path: str
    duration_ms: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: str = ""
    audio_codec: str = ""
    bitrate_kbps: Optional[int] = None
    audio_channels: Optional[int] = None
    media_created_epoch: Optional[int] = None
    probe_epoch: int = 0
    probe_status: str = "pending"
    probe_error: str = ""
    thumb_rel_path: str = ""
    thumb_width: Optional[int] = None
    thumb_height: Optional[int] = None
    frame_ms: Optional[int] = None
    source_mtime_epoch: Optional[int] = None
    generated_epoch: Optional[int] = None
    thumb_status: str = "pending"
    thumb_error: str = ""


@dataclass(frozen=True)
class ExplorerEntry:
    name: str
    rel_path: str
    is_dir: bool
    mtime_epoch: int = 0
    size_bytes: int = 0
    status: str = ""
    tags: list[str] = field(default_factory=list)
    ext: str = ""
    duration_ms: int = 0
    width: int = 0
    height: int = 0
    media_created_epoch: int = 0
    thumb_rel_path: str = ""
