from __future__ import annotations

import hashlib
import json
import locale
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.application.models import MediaRecord, ScanProgress, ScannedFile
from app.application.ports import ProgressCallback, ScanLoggerPort


class FfmpegMediaIndexer:
    def __init__(self, logger: Optional[ScanLoggerPort] = None) -> None:
        self._project_root = self._detect_project_root()
        self._ffmpeg_path: Optional[str] = None
        self._ffprobe_path: Optional[str] = None
        self._resolve_error: str = ""
        self._logger = logger
        self._resolve_binaries()

    def index(
        self,
        root: Path,
        scanned_files: list[ScannedFile],
        progress: Optional[ProgressCallback] = None,
    ) -> list[MediaRecord]:
        records: list[MediaRecord] = []
        now = int(time.time())
        total_steps = max(1, len(scanned_files) * 2)
        step = 0

        if not self._ffmpeg_path or not self._ffprobe_path:
            err = self._resolve_error or "ffmpeg/ffprobe 不可用"
            for item in scanned_files:
                step += 1
                self._emit_progress(
                    progress,
                    ScanProgress(
                        phase="media_probe",
                        message=f"FFmpeg 不可用，无法提取元数据：{item.filename}",
                        current=step,
                        total=total_steps,
                        indeterminate=False,
                        rel_path=item.rel_path,
                    ),
                )
                record = MediaRecord(
                    rel_path=item.rel_path,
                    source_mtime_epoch=item.mtime_epoch,
                    probe_epoch=now,
                    probe_status="error",
                    probe_error=err,
                    generated_epoch=now,
                    thumb_status="error",
                    thumb_error=err,
                )
                records.append(record)
                self._log_record(record)

                step += 1
                self._emit_progress(
                    progress,
                    ScanProgress(
                        phase="thumbnail",
                        message=f"FFmpeg 不可用，无法生成缩略图：{item.filename}",
                        current=step,
                        total=total_steps,
                        indeterminate=False,
                        rel_path=item.rel_path,
                    ),
                )
            return records

        thumbs_dir = root / ".mm" / "thumbs"
        thumbs_dir.mkdir(parents=True, exist_ok=True)

        for item in scanned_files:
            file_path = root / Path(item.rel_path)
            step += 1
            self._emit_progress(
                progress,
                ScanProgress(
                    phase="media_probe",
                    message=f"提取元数据 {step}/{total_steps}: {item.filename}",
                    current=step,
                    total=total_steps,
                    indeterminate=False,
                    rel_path=item.rel_path,
                ),
            )
            probe_data, probe_status, probe_error = self._probe_file(file_path)
            media = self._extract_media_info(probe_data)

            duration_ms = media.get("duration_ms") or 0
            frame_ms = self._select_frame_ms(duration_ms)
            thumb_rel_path = self._thumb_rel_path(item.rel_path)
            thumb_full_path = root / Path(thumb_rel_path)

            step += 1
            self._emit_progress(
                progress,
                ScanProgress(
                    phase="thumbnail",
                    message=f"生成缩略图 {step}/{total_steps}: {item.filename}",
                    current=step,
                    total=total_steps,
                    indeterminate=False,
                    rel_path=item.rel_path,
                ),
            )
            thumb_ok, thumb_error = self._generate_thumbnail(
                file_path=file_path,
                output_path=thumb_full_path,
                frame_ms=frame_ms,
            )

            record = MediaRecord(
                rel_path=item.rel_path,
                duration_ms=media.get("duration_ms"),
                width=media.get("width"),
                height=media.get("height"),
                fps=media.get("fps"),
                video_codec=media.get("video_codec", ""),
                audio_codec=media.get("audio_codec", ""),
                bitrate_kbps=media.get("bitrate_kbps"),
                audio_channels=media.get("audio_channels"),
                media_created_epoch=media.get("media_created_epoch")
                or int(file_path.stat().st_ctime),
                probe_epoch=now,
                probe_status=probe_status,
                probe_error=probe_error,
                thumb_rel_path=thumb_rel_path if thumb_ok else "",
                thumb_width=320 if thumb_ok else None,
                thumb_height=180 if thumb_ok else None,
                frame_ms=frame_ms,
                source_mtime_epoch=item.mtime_epoch,
                generated_epoch=now,
                thumb_status="ok" if thumb_ok else "error",
                thumb_error=thumb_error,
            )
            records.append(record)
            self._log_record(record)

        return records

    def _emit_progress(
        self, progress: Optional[ProgressCallback], event: ScanProgress
    ) -> None:
        if progress is None:
            return
        try:
            progress(event)
        except Exception:
            pass

    def _log_record(self, record: MediaRecord) -> None:
        if self._logger is None:
            return
        try:
            self._logger.log_media_record(record)
        except Exception:
            # Logging failures should never break scan.
            pass

    def _resolve_binaries(self) -> None:
        suffix = ".exe" if self._is_windows() else ""
        local_bin = self._project_root / "tools" / "ffmpeg" / "bin"
        local_ffmpeg = local_bin / f"ffmpeg{suffix}"
        local_ffprobe = local_bin / f"ffprobe{suffix}"

        ffmpeg_path = str(local_ffmpeg) if local_ffmpeg.exists() else shutil.which("ffmpeg")
        ffprobe_path = str(local_ffprobe) if local_ffprobe.exists() else shutil.which("ffprobe")

        if ffmpeg_path and ffprobe_path:
            self._ffmpeg_path = ffmpeg_path
            self._ffprobe_path = ffprobe_path
            return

        self._ffmpeg_path = None
        self._ffprobe_path = None
        self._resolve_error = (
            "未找到 ffmpeg/ffprobe。请将二进制放在 tools/ffmpeg/bin，或加入 PATH。"
        )

    def _probe_file(self, file_path: Path) -> tuple[dict[str, Any], str, str]:
        cmd = [
            str(self._ffprobe_path),
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            str(file_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=False, check=False)
            if proc.returncode != 0:
                return {}, "error", self._decode_output(proc.stderr) or "ffprobe 执行失败"
            data = self._parse_probe_json(proc.stdout)
            return data, "ok", ""
        except Exception as exc:
            return {}, "error", str(exc)

    def _extract_media_info(self, data: dict[str, Any]) -> dict[str, Any]:
        streams = data.get("streams") or []
        fmt = data.get("format") or {}
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

        duration_s = self._to_float(v_stream.get("duration"))
        if duration_s is None:
            duration_s = self._to_float(fmt.get("duration"))
        duration_ms = int(duration_s * 1000) if duration_s is not None else None

        bitrate = self._to_int(fmt.get("bit_rate"))
        bitrate_kbps = int(bitrate / 1000) if bitrate is not None else None

        created_epoch = self._parse_creation_time(
            (fmt.get("tags") or {}).get("creation_time")
            or (fmt.get("tags") or {}).get("com.apple.quicktime.creationdate")
            or (v_stream.get("tags") or {}).get("creation_time")
        )

        return {
            "duration_ms": duration_ms,
            "width": self._to_int(v_stream.get("width")),
            "height": self._to_int(v_stream.get("height")),
            "fps": self._parse_fps(str(v_stream.get("r_frame_rate") or "")),
            "video_codec": str(v_stream.get("codec_name") or ""),
            "audio_codec": str(a_stream.get("codec_name") or ""),
            "bitrate_kbps": bitrate_kbps,
            "audio_channels": self._to_int(a_stream.get("channels")),
            "media_created_epoch": created_epoch,
        }

    def _generate_thumbnail(
        self, file_path: Path, output_path: Path, frame_ms: int
    ) -> tuple[bool, str]:
        frame_s = max(0.0, frame_ms / 1000.0)
        cmd = [
            str(self._ffmpeg_path),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{frame_s:.3f}",
            "-i",
            str(file_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2",
            "-q:v",
            "3",
            str(output_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=False, check=False)
            if proc.returncode != 0:
                return False, self._decode_output(proc.stderr) or "ffmpeg 执行失败"
            return output_path.exists(), ""
        except Exception as exc:
            return False, str(exc)

    def _parse_probe_json(self, raw: bytes) -> dict[str, Any]:
        if not raw:
            return {}
        encodings = self._candidate_encodings()
        last_error = ""
        for enc in encodings:
            try:
                text = raw.decode(enc)
                return json.loads(text or "{}")
            except Exception as exc:
                last_error = str(exc)
                continue
        text = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(text or "{}")
        except Exception as exc:
            raise ValueError(f"ffprobe JSON 解析失败: {last_error or str(exc)}")

    def _decode_output(self, raw: bytes) -> str:
        if not raw:
            return ""
        for enc in self._candidate_encodings():
            try:
                return raw.decode(enc).strip()
            except Exception:
                continue
        return raw.decode("utf-8", errors="replace").strip()

    def _candidate_encodings(self) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for enc in ["utf-8", locale.getpreferredencoding(False), "gbk"]:
            name = (enc or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(name)
        return found

    def _thumb_rel_path(self, rel_path: str) -> str:
        digest = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()
        return f".mm/thumbs/{digest}.jpg"

    def _select_frame_ms(self, duration_ms: int) -> int:
        if duration_ms <= 0:
            return 1000
        if duration_ms < 10_000:
            return 1000
        return int(duration_ms * 0.1)

    def _parse_creation_time(self, value: Any) -> Optional[int]:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        text = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
            return int(dt.timestamp())
        except Exception:
            return None

    def _parse_fps(self, ratio: str) -> Optional[float]:
        if not ratio or ratio == "0/0":
            return None
        if "/" not in ratio:
            return self._to_float(ratio)
        left, right = ratio.split("/", 1)
        n = self._to_float(left)
        d = self._to_float(right)
        if n is None or d in (None, 0):
            return None
        return n / d

    def _to_int(self, value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(float(str(value)))
        except Exception:
            return None

    def _to_float(self, value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(str(value))
        except Exception:
            return None

    def _is_windows(self) -> bool:
        return os.name == "nt"

    def _detect_project_root(self) -> Path:
        # PyInstaller: put tools/ beside executable for stable lookup.
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]
