from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from app.application.models import MediaRecord, ScanResult, ScannedFile


LIB_DIRNAME = ".mm"
DB_FILENAME = "library.db"
DB_VERSION = 5
_CANDIDATE_STATUSES = {"pending", "approved", "blacklisted", "mapped"}


def _now_epoch() -> int:
    return int(time.time())


def _normalize_lookup_key(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "")


class SqliteLibraryRepository:
    def __init__(self) -> None:
        self._root: Optional[Path] = None
        self._db_path: Optional[Path] = None
        self._conn: Optional[sqlite3.Connection] = None
        self._data: Dict[str, Any] = {}

    def open(self, root: Path) -> None:
        self.close()

        lib_dir = root / LIB_DIRNAME
        lib_dir.mkdir(parents=True, exist_ok=True)

        db_path = lib_dir / DB_FILENAME
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")

        self._root = root
        self._db_path = db_path
        self._conn = conn

        self._create_schema()
        self._migrate_schema()
        self._bootstrap_meta()
        self._load_data()

    def close(self) -> None:
        conn = self._conn
        self._conn = None
        self._root = None
        self._db_path = None
        self._data = {}
        if conn is None:
            return
        try:
            # Best-effort checkpoint helps release WAL-related file locks sooner on Windows.
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    def root_path(self) -> Optional[Path]:
        return self._root

    def raw_data(self) -> Dict[str, Any]:
        return self._data

    def videos(self) -> Dict[str, Dict[str, Any]]:
        videos = self._data.get("videos")
        if isinstance(videos, dict):
            return videos
        return {}

    def save(self) -> None:
        conn = self._require_conn()
        now = _now_epoch()
        videos = self.videos()

        existing_rows = conn.execute(
            "SELECT id, missing, missing_since_epoch, created_at_epoch FROM videos"
        ).fetchall()
        existing = {
            str(row["id"]): {
                "missing": int(row["missing"] or 0),
                "missing_since_epoch": row["missing_since_epoch"],
                "created_at_epoch": int(row["created_at_epoch"] or now),
            }
            for row in existing_rows
        }

        with conn:
            for vid, info in videos.items():
                rel_path = str(info.get("rel_path") or "")
                filename = str(info.get("filename") or Path(rel_path).name)
                ext = str(info.get("ext") or Path(filename).suffix.lower().lstrip("."))
                size_bytes = int(info.get("size_bytes") or 0)
                mtime_epoch = int(info.get("mtime_epoch") or 0)
                added_at_epoch = int(info.get("added_at_epoch") or now)
                last_seen_epoch = int(info.get("last_seen_epoch") or now)
                missing = 1 if info.get("missing") else 0
                title_guess = str(info.get("title_guess") or filename)
                status = str(info.get("status") or "")
                notes = str(info.get("notes") or "")
                title_tag_mined_epoch = int(info.get("title_tag_mined_epoch") or 0)

                prev = existing.get(vid)
                if prev:
                    created_at_epoch = int(prev["created_at_epoch"])
                    prev_missing = int(prev["missing"])
                    prev_missing_since = prev["missing_since_epoch"]
                else:
                    created_at_epoch = now
                    prev_missing = 0
                    prev_missing_since = None

                if missing:
                    missing_since_epoch = (
                        now if (prev_missing == 0 or prev_missing_since is None) else prev_missing_since
                    )
                else:
                    missing_since_epoch = None

                conn.execute(
                    """
                    INSERT INTO videos (
                        id, rel_path, filename, ext, size_bytes, mtime_epoch,
                        added_at_epoch, last_seen_epoch, missing, missing_since_epoch,
                        title_guess, status, notes, title_tag_mined_epoch,
                        created_at_epoch, updated_at_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        rel_path = excluded.rel_path,
                        filename = excluded.filename,
                        ext = excluded.ext,
                        size_bytes = excluded.size_bytes,
                        mtime_epoch = excluded.mtime_epoch,
                        added_at_epoch = excluded.added_at_epoch,
                        last_seen_epoch = excluded.last_seen_epoch,
                        missing = excluded.missing,
                        missing_since_epoch = excluded.missing_since_epoch,
                        title_guess = excluded.title_guess,
                        status = excluded.status,
                        notes = excluded.notes,
                        title_tag_mined_epoch = excluded.title_tag_mined_epoch,
                        updated_at_epoch = excluded.updated_at_epoch
                    """,
                    (
                        vid,
                        rel_path,
                        filename,
                        ext,
                        size_bytes,
                        mtime_epoch,
                        added_at_epoch,
                        last_seen_epoch,
                        missing,
                        missing_since_epoch,
                        title_guess,
                        status,
                        notes,
                        title_tag_mined_epoch,
                        created_at_epoch,
                        now,
                    ),
                )

                self._upsert_video_tags(conn, vid, info.get("tags") or [], now)

            self._set_meta(conn, "updated_at", str(now))

        self._load_data()

    def apply_scan(self, scanned_files: list[ScannedFile]) -> ScanResult:
        conn = self._require_conn()
        now = _now_epoch()
        refresh_rel_paths: list[str] = []

        with conn:
            conn.execute(
                """
                CREATE TEMP TABLE IF NOT EXISTS scan_input (
                    rel_path TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    ext TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mtime_epoch INTEGER NOT NULL
                )
                """
            )
            conn.execute("DELETE FROM scan_input")
            conn.executemany(
                """
                INSERT INTO scan_input(rel_path, filename, ext, size_bytes, mtime_epoch)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.rel_path,
                        item.filename,
                        item.ext,
                        int(item.size_bytes),
                        int(item.mtime_epoch),
                    )
                    for item in scanned_files
                ],
            )

            seen = int(
                conn.execute("SELECT COUNT(*) AS c FROM scan_input").fetchone()["c"]
            )
            added = int(
                conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM scan_input s
                    LEFT JOIN videos v ON v.rel_path = s.rel_path
                    WHERE v.id IS NULL
                    """
                ).fetchone()["c"]
            )
            updated = int(
                conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM scan_input s
                    JOIN videos v ON v.rel_path = s.rel_path
                    WHERE v.size_bytes != s.size_bytes OR v.mtime_epoch != s.mtime_epoch
                    """
                ).fetchone()["c"]
            )
            refresh_rows = conn.execute(
                """
                SELECT s.rel_path
                FROM scan_input s
                LEFT JOIN videos v ON v.rel_path = s.rel_path
                WHERE v.id IS NULL
                   OR v.size_bytes != s.size_bytes
                   OR v.mtime_epoch != s.mtime_epoch
                """
            ).fetchall()
            refresh_rel_paths = [str(row["rel_path"]) for row in refresh_rows]

            new_rows = conn.execute(
                """
                SELECT s.rel_path, s.filename, s.ext, s.size_bytes, s.mtime_epoch
                FROM scan_input s
                LEFT JOIN videos v ON v.rel_path = s.rel_path
                WHERE v.id IS NULL
                """
            ).fetchall()
            for row in new_rows:
                vid = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO videos (
                        id, rel_path, filename, ext, size_bytes, mtime_epoch,
                        added_at_epoch, last_seen_epoch, missing, missing_since_epoch,
                        title_guess, status, notes, title_tag_mined_epoch,
                        created_at_epoch, updated_at_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        vid,
                        str(row["rel_path"]),
                        str(row["filename"]),
                        str(row["ext"]),
                        int(row["size_bytes"]),
                        int(row["mtime_epoch"]),
                        now,
                        now,
                        0,
                        None,
                        str(row["filename"]),
                        "",
                        "",
                        0,
                        now,
                        now,
                    ),
                )

            conn.execute(
                """
                UPDATE videos
                SET
                    filename = (SELECT s.filename FROM scan_input s WHERE s.rel_path = videos.rel_path),
                    ext = (SELECT s.ext FROM scan_input s WHERE s.rel_path = videos.rel_path),
                    size_bytes = (SELECT s.size_bytes FROM scan_input s WHERE s.rel_path = videos.rel_path),
                    mtime_epoch = (SELECT s.mtime_epoch FROM scan_input s WHERE s.rel_path = videos.rel_path),
                    last_seen_epoch = ?,
                    missing = 0,
                    missing_since_epoch = NULL,
                    updated_at_epoch = ?
                WHERE rel_path IN (SELECT rel_path FROM scan_input)
                """,
                (now, now),
            )

            conn.execute(
                """
                UPDATE videos
                SET
                    missing = 1,
                    missing_since_epoch = COALESCE(missing_since_epoch, ?),
                    updated_at_epoch = ?
                WHERE rel_path NOT IN (SELECT rel_path FROM scan_input)
                """,
                (now, now),
            )

            self._set_meta(conn, "updated_at", str(now))

        self._load_data()
        return ScanResult(
            added=added,
            updated=updated,
            seen=seen,
            refresh_rel_paths=refresh_rel_paths,
        )

    def apply_media_records(self, media_records: list[MediaRecord]) -> None:
        if not media_records:
            return

        conn = self._require_conn()
        now = _now_epoch()
        with conn:
            for record in media_records:
                row = conn.execute(
                    "SELECT id FROM videos WHERE rel_path = ?",
                    (record.rel_path,),
                ).fetchone()
                if row is None:
                    continue
                video_id = str(row["id"])

                conn.execute(
                    """
                    INSERT INTO video_media(
                        video_id, duration_ms, width, height, fps, video_codec, audio_codec,
                        bitrate_kbps, audio_channels, media_created_epoch, probe_epoch,
                        probe_status, probe_error, extra_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(video_id) DO UPDATE SET
                        duration_ms = excluded.duration_ms,
                        width = excluded.width,
                        height = excluded.height,
                        fps = excluded.fps,
                        video_codec = excluded.video_codec,
                        audio_codec = excluded.audio_codec,
                        bitrate_kbps = excluded.bitrate_kbps,
                        audio_channels = excluded.audio_channels,
                        media_created_epoch = excluded.media_created_epoch,
                        probe_epoch = excluded.probe_epoch,
                        probe_status = excluded.probe_status,
                        probe_error = excluded.probe_error,
                        extra_json = excluded.extra_json
                    """,
                    (
                        video_id,
                        record.duration_ms,
                        record.width,
                        record.height,
                        record.fps,
                        record.video_codec,
                        record.audio_codec,
                        record.bitrate_kbps,
                        record.audio_channels,
                        record.media_created_epoch,
                        record.probe_epoch,
                        record.probe_status,
                        record.probe_error,
                        "",
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO thumbnails(
                        video_id, thumb_rel_path, width, height, frame_ms, source_mtime_epoch,
                        generated_epoch, generator, status, error_msg
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(video_id) DO UPDATE SET
                        thumb_rel_path = excluded.thumb_rel_path,
                        width = excluded.width,
                        height = excluded.height,
                        frame_ms = excluded.frame_ms,
                        source_mtime_epoch = excluded.source_mtime_epoch,
                        generated_epoch = excluded.generated_epoch,
                        generator = excluded.generator,
                        status = excluded.status,
                        error_msg = excluded.error_msg
                    """,
                    (
                        video_id,
                        record.thumb_rel_path,
                        record.thumb_width,
                        record.thumb_height,
                        record.frame_ms,
                        record.source_mtime_epoch,
                        record.generated_epoch,
                        "ffmpeg",
                        record.thumb_status,
                        record.thumb_error,
                    ),
                )

            self._set_meta(conn, "updated_at", str(now))

        self._load_data()

    def apply_ai_title_tags(
        self,
        tags_by_video_id: Dict[str, list[str]],
        target_video_ids: Optional[list[str]] = None,
    ) -> int:
        conn = self._require_conn()
        now = _now_epoch()
        created_relations = 0
        touched_video_ids = sorted(
            {
                str(video_id)
                for video_id in (target_video_ids or list(tags_by_video_id.keys()))
                if str(video_id).strip()
            }
        )
        if not touched_video_ids:
            return 0

        placeholders = ", ".join(["?"] * len(touched_video_ids))

        with conn:
            tag_rows = conn.execute("SELECT id, name FROM tags").fetchall()
            tag_id_by_name = {
                str(row["name"]).strip().lower(): int(row["id"])
                for row in tag_rows
                if str(row["name"]).strip()
            }
            conn.execute(
                f"""
                DELETE FROM video_tags
                WHERE source = 'ai_title'
                  AND video_id IN ({placeholders})
                """,
                tuple(touched_video_ids),
            )

            for video_id in touched_video_ids:
                row = conn.execute(
                    "SELECT 1 FROM videos WHERE id = ?",
                    (video_id,),
                ).fetchone()
                if row is None:
                    continue

                normalized_tags = self._normalize_tag_names(
                    list(tags_by_video_id.get(video_id) or [])
                )
                for tag_name in normalized_tags:
                    tag_id = tag_id_by_name.get(tag_name.lower())
                    if tag_id is None:
                        continue
                    conn.execute(
                        """
                        INSERT INTO video_tags(video_id, tag_id, source, confidence, created_at_epoch, updated_at_epoch)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(video_id, tag_id, source) DO UPDATE SET
                            confidence = excluded.confidence,
                            updated_at_epoch = excluded.updated_at_epoch
                        """,
                        (video_id, tag_id, "ai_title", 0.80, now, now),
                    )
                    created_relations += 1

            self._set_meta(conn, "updated_at", str(now))

        self._load_data()
        return created_relations

    def clear_ai_title_tags(self) -> int:
        conn = self._require_conn()
        now = _now_epoch()
        with conn:
            removed = int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM video_tags WHERE source = 'ai_title'"
                ).fetchone()["c"]
            )
            conn.execute("DELETE FROM video_tags WHERE source = 'ai_title'")
            self._set_meta(conn, "updated_at", str(now))
        self._load_data()
        return removed

    def mark_title_tag_mined(self, video_ids: list[str], mined_epoch: int) -> None:
        conn = self._require_conn()
        unique_ids = sorted(
            {str(video_id) for video_id in video_ids if str(video_id).strip()}
        )
        if not unique_ids:
            return

        placeholders = ", ".join(["?"] * len(unique_ids))
        now = _now_epoch()
        with conn:
            conn.execute(
                f"""
                UPDATE videos
                SET title_tag_mined_epoch = ?, updated_at_epoch = ?
                WHERE id IN ({placeholders})
                """,
                (int(mined_epoch), now, *tuple(unique_ids)),
            )
            self._set_meta(conn, "updated_at", str(now))
        self._load_data()

    def upsert_tag_candidates(self, hits_by_tag: Dict[str, list[str]]) -> int:
        conn = self._require_conn()
        if not hits_by_tag:
            return 0

        now = _now_epoch()
        touched = 0
        with conn:
            blacklist_keys = self._prepare_blacklist_keys(
                [str(row["term"] or "") for row in conn.execute("SELECT term FROM tag_blacklist")]
            )
            for raw_name, raw_video_ids in hits_by_tag.items():
                clean_names = self._normalize_tag_names([raw_name])
                if not clean_names:
                    continue
                tag_name = clean_names[0]
                if self._matches_blacklist_term(tag_name, blacklist_keys):
                    continue
                unique_video_ids = sorted(
                    {str(video_id) for video_id in raw_video_ids if str(video_id).strip()}
                )
                if not unique_video_ids:
                    continue

                row = conn.execute(
                    "SELECT id, status FROM tag_candidates WHERE name = ?",
                    (tag_name,),
                ).fetchone()
                if row is None:
                    cur = conn.execute(
                        """
                        INSERT INTO tag_candidates(name, status, first_seen_epoch, last_seen_epoch, hit_count)
                        VALUES (?, 'pending', ?, ?, 0)
                        """,
                        (tag_name, now, now),
                    )
                    candidate_id = int(cur.lastrowid or 0)
                    status = "pending"
                else:
                    candidate_id = int(row["id"])
                    status = str(row["status"] or "pending")
                    conn.execute(
                        "UPDATE tag_candidates SET last_seen_epoch = ? WHERE id = ?",
                        (now, candidate_id),
                    )

                if candidate_id <= 0 or status != "pending":
                    continue

                for video_id in unique_video_ids:
                    conn.execute(
                        """
                        INSERT INTO tag_candidate_hits(candidate_id, video_id, created_at_epoch)
                        SELECT ?, ?, ?
                        WHERE EXISTS (SELECT 1 FROM videos WHERE id = ?)
                        ON CONFLICT(candidate_id, video_id) DO NOTHING
                        """,
                        (candidate_id, video_id, now, video_id),
                    )

                hit_count = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM tag_candidate_hits
                        WHERE candidate_id = ?
                        """,
                        (candidate_id,),
                    ).fetchone()["c"]
                )
                conn.execute(
                    """
                    UPDATE tag_candidates
                    SET hit_count = ?, last_seen_epoch = ?
                    WHERE id = ?
                    """,
                    (hit_count, now, candidate_id),
                )
                touched += 1

            if touched > 0:
                self._set_meta(conn, "updated_at", str(now))

        return touched

    def list_tag_candidates(self, statuses: Optional[list[str]] = None) -> list[Dict[str, Any]]:
        conn = self._require_conn()
        filtered_statuses: list[str] = []
        seen = set()
        for raw_status in list(statuses or []):
            status = str(raw_status or "").strip().lower()
            if not status or status in seen:
                continue
            if status not in _CANDIDATE_STATUSES:
                continue
            seen.add(status)
            filtered_statuses.append(status)

        where_clause = ""
        params: tuple[Any, ...] = ()
        if filtered_statuses:
            placeholders = ", ".join(["?"] * len(filtered_statuses))
            where_clause = f"WHERE status IN ({placeholders})"
            params = tuple(filtered_statuses)

        rows = conn.execute(
            f"""
            SELECT
                id,
                name,
                status,
                mapped_tag_id,
                first_seen_epoch,
                last_seen_epoch,
                hit_count
            FROM tag_candidates
            {where_clause}
            ORDER BY
                CASE status
                    WHEN 'pending' THEN 0
                    WHEN 'blacklisted' THEN 1
                    WHEN 'approved' THEN 2
                    WHEN 'mapped' THEN 3
                    ELSE 4
                END,
                hit_count DESC,
                last_seen_epoch DESC,
                name COLLATE NOCASE
            """,
            params,
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "status": str(row["status"] or "pending"),
                "mapped_tag_id": int(row["mapped_tag_id"] or 0),
                "first_seen_epoch": int(row["first_seen_epoch"] or 0),
                "last_seen_epoch": int(row["last_seen_epoch"] or 0),
                "hit_count": int(row["hit_count"] or 0),
            }
            for row in rows
        ]

    def list_pending_tag_candidates(self) -> list[Dict[str, Any]]:
        return self.list_tag_candidates(statuses=["pending"])

    def list_tag_blacklist(self) -> list[Dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT
                id,
                term,
                source,
                reason,
                hit_count,
                first_seen_epoch,
                last_seen_epoch
            FROM tag_blacklist
            ORDER BY hit_count DESC, last_seen_epoch DESC, term COLLATE NOCASE
            """
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "term": str(row["term"] or ""),
                "source": str(row["source"] or "manual"),
                "reason": str(row["reason"] or ""),
                "hit_count": int(row["hit_count"] or 0),
                "first_seen_epoch": int(row["first_seen_epoch"] or 0),
                "last_seen_epoch": int(row["last_seen_epoch"] or 0),
            }
            for row in rows
        ]

    def list_blacklist_terms(self) -> list[str]:
        return [
            str(item.get("term") or "")
            for item in self.list_tag_blacklist()
            if str(item.get("term") or "").strip()
        ]

    def blacklist_tag_candidates(self, candidate_ids: list[int]) -> Dict[str, int]:
        conn = self._require_conn()
        unique_ids = sorted({int(candidate_id) for candidate_id in candidate_ids if int(candidate_id) > 0})
        if not unique_ids:
            return {"blacklisted_candidates": 0, "blacklist_terms_added": 0}

        placeholders = ", ".join(["?"] * len(unique_ids))
        now = _now_epoch()
        blacklisted = 0
        terms_added = 0
        with conn:
            rows = conn.execute(
                f"""
                SELECT id, name
                FROM tag_candidates
                WHERE id IN ({placeholders})
                  AND status = 'pending'
                """,
                tuple(unique_ids),
            ).fetchall()
            for row in rows:
                candidate_id = int(row["id"])
                candidate_name = str(row["name"] or "").strip()
                if candidate_name and self._upsert_blacklist_term_row(
                    conn=conn,
                    term=candidate_name,
                    source="candidate_review",
                    reason="from_candidate",
                    now=now,
                ):
                    terms_added += 1
                conn.execute(
                    """
                    UPDATE tag_candidates
                    SET status = 'blacklisted', mapped_tag_id = NULL, last_seen_epoch = ?
                    WHERE id = ?
                    """,
                    (now, candidate_id),
                )
                blacklisted += 1

            if blacklisted > 0:
                self._set_meta(conn, "updated_at", str(now))

        if blacklisted > 0:
            self._load_data()
        return {
            "blacklisted_candidates": blacklisted,
            "blacklist_terms_added": terms_added,
        }

    def clear_pending_tag_candidates(self) -> int:
        conn = self._require_conn()
        now = _now_epoch()
        with conn:
            conn.execute("DELETE FROM tag_candidates WHERE status = 'pending'")
            removed = int(conn.execute("SELECT changes() AS c").fetchone()["c"])
            if removed > 0:
                self._set_meta(conn, "updated_at", str(now))
        if removed > 0:
            self._load_data()
        return removed

    def approve_tag_candidates(self, candidate_ids: list[int]) -> Dict[str, int]:
        conn = self._require_conn()
        unique_ids = sorted({int(candidate_id) for candidate_id in candidate_ids if int(candidate_id) > 0})
        if not unique_ids:
            return {"approved_candidates": 0, "applied_relations": 0}

        placeholders = ", ".join(["?"] * len(unique_ids))
        now = _now_epoch()
        approved = 0
        applied_relations = 0
        with conn:
            rows = conn.execute(
                f"""
                SELECT id, name
                FROM tag_candidates
                WHERE id IN ({placeholders})
                  AND status = 'pending'
                """,
                tuple(unique_ids),
            ).fetchall()
            for row in rows:
                candidate_id = int(row["id"])
                tag_name = str(row["name"])
                conn.execute(
                    "INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING",
                    (tag_name,),
                )
                tag_row = conn.execute(
                    "SELECT id FROM tags WHERE name = ?",
                    (tag_name,),
                ).fetchone()
                if tag_row is None:
                    continue
                tag_id = int(tag_row["id"])
                hit_rows = conn.execute(
                    """
                    SELECT video_id
                    FROM tag_candidate_hits
                    WHERE candidate_id = ?
                    """,
                    (candidate_id,),
                ).fetchall()
                for hit in hit_rows:
                    video_id = str(hit["video_id"])
                    conn.execute(
                        """
                        INSERT INTO video_tags(video_id, tag_id, source, confidence, created_at_epoch, updated_at_epoch)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(video_id, tag_id, source) DO UPDATE SET
                            confidence = excluded.confidence,
                            updated_at_epoch = excluded.updated_at_epoch
                        """,
                        (video_id, tag_id, "ai_title", 0.75, now, now),
                    )
                    applied_relations += 1

                conn.execute(
                    """
                    UPDATE tag_candidates
                    SET status = 'approved', mapped_tag_id = ?, last_seen_epoch = ?
                    WHERE id = ?
                    """,
                    (tag_id, now, candidate_id),
                )
                approved += 1

            if approved > 0:
                self._set_meta(conn, "updated_at", str(now))

        if approved > 0:
            self._load_data()
        return {"approved_candidates": approved, "applied_relations": applied_relations}

    def approve_tag_candidates_with_mapping(
        self,
        candidate_ids: list[int],
        target_tag_id: int,
    ) -> Dict[str, int]:
        conn = self._require_conn()
        unique_ids = sorted(
            {int(candidate_id) for candidate_id in candidate_ids if int(candidate_id) > 0}
        )
        mapped_tag_id = int(target_tag_id or 0)
        if not unique_ids or mapped_tag_id <= 0:
            return {"approved_candidates": 0, "applied_relations": 0, "alias_memory_written": 0}

        tag_row = conn.execute(
            "SELECT id FROM tags WHERE id = ?",
            (mapped_tag_id,),
        ).fetchone()
        if tag_row is None:
            return {"approved_candidates": 0, "applied_relations": 0, "alias_memory_written": 0}

        placeholders = ", ".join(["?"] * len(unique_ids))
        now = _now_epoch()
        approved = 0
        applied_relations = 0
        alias_memory_written = 0
        with conn:
            rows = conn.execute(
                f"""
                SELECT id, name
                FROM tag_candidates
                WHERE id IN ({placeholders})
                  AND status = 'pending'
                """,
                tuple(unique_ids),
            ).fetchall()
            for row in rows:
                candidate_id = int(row["id"])
                candidate_name = str(row["name"] or "").strip()
                hit_rows = conn.execute(
                    """
                    SELECT video_id
                    FROM tag_candidate_hits
                    WHERE candidate_id = ?
                    """,
                    (candidate_id,),
                ).fetchall()
                for hit in hit_rows:
                    video_id = str(hit["video_id"])
                    conn.execute(
                        """
                        INSERT INTO video_tags(video_id, tag_id, source, confidence, created_at_epoch, updated_at_epoch)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(video_id, tag_id, source) DO UPDATE SET
                            confidence = excluded.confidence,
                            updated_at_epoch = excluded.updated_at_epoch
                        """,
                        (video_id, mapped_tag_id, "ai_title", 0.78, now, now),
                    )
                    applied_relations += 1

                if candidate_name:
                    created = self._upsert_tag_alias_row(
                        conn=conn,
                        alias=candidate_name,
                        tag_id=mapped_tag_id,
                        confidence=0.9,
                        source="candidate_review",
                        status="verified",
                        now=now,
                    )
                    if created:
                        alias_memory_written += 1

                conn.execute(
                    """
                    UPDATE tag_candidates
                    SET status = 'mapped', mapped_tag_id = ?, last_seen_epoch = ?
                    WHERE id = ?
                    """,
                    (mapped_tag_id, now, candidate_id),
                )
                approved += 1

            if approved > 0:
                self._set_meta(conn, "updated_at", str(now))

        if approved > 0:
            self._load_data()
        return {
            "approved_candidates": approved,
            "applied_relations": applied_relations,
            "alias_memory_written": alias_memory_written,
        }

    def reject_tag_candidates(self, candidate_ids: list[int]) -> int:
        # Backward compatibility: "reject" now means "move to blacklist".
        result = self.blacklist_tag_candidates(candidate_ids)
        return int(result.get("blacklisted_candidates") or 0)

    def requeue_tag_candidates(self, candidate_ids: list[int]) -> int:
        conn = self._require_conn()
        unique_ids = sorted({int(candidate_id) for candidate_id in candidate_ids if int(candidate_id) > 0})
        if not unique_ids:
            return 0

        placeholders = ", ".join(["?"] * len(unique_ids))
        now = _now_epoch()
        with conn:
            cur = conn.execute(
                f"""
                UPDATE tag_candidates
                SET status = 'pending', last_seen_epoch = ?
                WHERE id IN ({placeholders})
                  AND status = 'blacklisted'
                """,
                (now, *tuple(unique_ids)),
            )
            affected = int(cur.rowcount or 0)
            if affected > 0:
                self._set_meta(conn, "updated_at", str(now))
        return affected

    def list_tags(self) -> list[Dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT
                t.id AS id,
                t.name AS name,
                COUNT(vt.video_id) AS usage_count,
                SUM(CASE WHEN vt.source = 'manual' THEN 1 ELSE 0 END) AS manual_usage_count,
                SUM(CASE WHEN vt.source = 'ai_title' THEN 1 ELSE 0 END) AS ai_usage_count
            FROM tags t
            LEFT JOIN video_tags vt ON vt.tag_id = t.id
            GROUP BY t.id, t.name
            ORDER BY t.name COLLATE NOCASE
            """
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "usage_count": int(row["usage_count"] or 0),
                "manual_usage_count": int(row["manual_usage_count"] or 0),
                "ai_usage_count": int(row["ai_usage_count"] or 0),
            }
            for row in rows
        ]

    def list_concept_mappings(self) -> list[Dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT
                c.id AS concept_id,
                c.name AS concept_name,
                c.status AS concept_status,
                c.source AS concept_source,
                ca.alias AS alias_name,
                ca.confidence AS alias_confidence,
                t.name AS tag_name,
                ctl.weight AS link_weight,
                ctl.relation AS link_relation
            FROM concepts c
            LEFT JOIN concept_aliases ca ON ca.concept_id = c.id
            LEFT JOIN concept_tag_links ctl ON ctl.concept_id = c.id
            LEFT JOIN tags t ON t.id = ctl.tag_id
            WHERE c.status = 'active'
            ORDER BY c.name COLLATE NOCASE, ca.alias COLLATE NOCASE, t.name COLLATE NOCASE
            """
        ).fetchall()

        concepts: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            concept_id = int(row["concept_id"])
            item = concepts.get(concept_id)
            if item is None:
                item = {
                    "id": concept_id,
                    "name": str(row["concept_name"] or ""),
                    "status": str(row["concept_status"] or "active"),
                    "source": str(row["concept_source"] or "manual"),
                    "aliases": [],
                    "tags": [],
                }
                concepts[concept_id] = item

            alias_name = str(row["alias_name"] or "").strip()
            if alias_name and alias_name not in item["aliases"]:
                item["aliases"].append(alias_name)
            tag_name = str(row["tag_name"] or "").strip()
            if tag_name and tag_name not in item["tags"]:
                item["tags"].append(tag_name)

        all_tags = self.list_tags()
        seen_tag_keys = {
            str(tag_name).strip().lower()
            for item in concepts.values()
            for tag_name in list(item.get("tags") or [])
            if str(tag_name).strip()
        }
        fallback_id_seed = -1
        for tag in all_tags:
            tag_name = str(tag.get("name") or "").strip()
            if not tag_name:
                continue
            tag_key = tag_name.lower()
            if tag_key in seen_tag_keys:
                continue
            concepts[fallback_id_seed] = {
                "id": fallback_id_seed,
                "name": tag_name,
                "status": "active",
                "source": "fallback_tag",
                "aliases": [tag_name],
                "tags": [tag_name],
            }
            fallback_id_seed -= 1

        out = list(concepts.values())
        out.sort(key=lambda item: str(item.get("name") or "").lower())
        return out

    def list_tag_alias_memory(self) -> list[Dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT
                tam.id AS id,
                tam.alias AS alias,
                tam.tag_id AS tag_id,
                t.name AS tag_name,
                tam.confidence AS confidence,
                tam.status AS status,
                tam.source AS source,
                tam.hit_count AS hit_count,
                tam.first_mapped_epoch AS first_mapped_epoch,
                tam.last_mapped_epoch AS last_mapped_epoch,
                tam.created_at_epoch AS created_at_epoch,
                tam.updated_at_epoch AS updated_at_epoch
            FROM tag_alias_memory tam
            JOIN tags t ON t.id = tam.tag_id
            ORDER BY tam.hit_count DESC, tam.last_mapped_epoch DESC, tam.alias COLLATE NOCASE
            """
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "alias": str(row["alias"] or ""),
                "tag_id": int(row["tag_id"] or 0),
                "tag_name": str(row["tag_name"] or ""),
                "confidence": float(row["confidence"] or 0.0),
                "status": str(row["status"] or "verified"),
                "source": str(row["source"] or "manual"),
                "hit_count": int(row["hit_count"] or 0),
                "first_mapped_epoch": int(row["first_mapped_epoch"] or 0),
                "last_mapped_epoch": int(row["last_mapped_epoch"] or 0),
                "created_at_epoch": int(row["created_at_epoch"] or 0),
                "updated_at_epoch": int(row["updated_at_epoch"] or 0),
            }
            for row in rows
        ]

    def upsert_tag_alias_memory(
        self,
        alias_to_tag_id: Dict[str, int],
        source: str = "manual",
        status: str = "verified",
    ) -> int:
        conn = self._require_conn()
        if not alias_to_tag_id:
            return 0

        safe_source = str(source or "manual").strip() or "manual"
        safe_status = str(status or "verified").strip().lower() or "verified"
        if safe_status not in {"verified", "auto_pending", "disabled"}:
            safe_status = "verified"

        now = _now_epoch()
        touched = 0
        with conn:
            for raw_alias, raw_tag_id in alias_to_tag_id.items():
                alias = str(raw_alias or "").strip()
                if len(alias) < 2:
                    continue
                try:
                    tag_id = int(raw_tag_id)
                except Exception:
                    continue
                if tag_id <= 0:
                    continue
                tag_row = conn.execute(
                    "SELECT id FROM tags WHERE id = ?",
                    (tag_id,),
                ).fetchone()
                if tag_row is None:
                    continue
                created = self._upsert_tag_alias_row(
                    conn=conn,
                    alias=alias,
                    tag_id=tag_id,
                    confidence=1.0 if safe_status == "verified" else 0.8,
                    source=safe_source,
                    status=safe_status,
                    now=now,
                )
                if created:
                    touched += 1
            if touched > 0:
                self._set_meta(conn, "updated_at", str(now))
        return touched

    def upsert_tag_alias_suggestions(
        self, suggestions: list[Dict[str, Any]]
    ) -> int:
        conn = self._require_conn()
        if not suggestions:
            return 0

        now = _now_epoch()
        touched = 0
        with conn:
            for item in suggestions:
                alias = str(item.get("alias") or "").strip()
                if len(alias) < 2:
                    continue
                try:
                    target_tag_id = int(item.get("target_tag_id") or 0)
                except Exception:
                    target_tag_id = 0
                if target_tag_id <= 0:
                    continue
                tag_row = conn.execute(
                    "SELECT id FROM tags WHERE id = ?",
                    (target_tag_id,),
                ).fetchone()
                if tag_row is None:
                    continue

                score = float(item.get("score") or 0.0)
                source = str(item.get("source") or "model").strip() or "model"
                reason = str(item.get("reason") or "").strip()
                row = conn.execute(
                    """
                    SELECT id, hit_count
                    FROM tag_alias_suggestions
                    WHERE alias = ? AND target_tag_id = ? AND status = 'pending'
                    """,
                    (alias, target_tag_id),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO tag_alias_suggestions(
                            alias, target_tag_id, score, source, reason, status,
                            hit_count, first_seen_epoch, last_seen_epoch, created_at_epoch, updated_at_epoch
                        )
                        VALUES (?, ?, ?, ?, ?, 'pending', 1, ?, ?, ?, ?)
                        """,
                        (alias, target_tag_id, score, source, reason, now, now, now, now),
                    )
                    touched += 1
                    continue

                suggestion_id = int(row["id"])
                hit_count = int(row["hit_count"] or 0) + 1
                conn.execute(
                    """
                    UPDATE tag_alias_suggestions
                    SET score = ?, source = ?, reason = ?, hit_count = ?, last_seen_epoch = ?, updated_at_epoch = ?
                    WHERE id = ?
                    """,
                    (score, source, reason, hit_count, now, now, suggestion_id),
                )
                touched += 1

            if touched > 0:
                self._set_meta(conn, "updated_at", str(now))
        return touched

    def list_pending_tag_alias_suggestions(self) -> list[Dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT
                tas.id AS id,
                tas.alias AS alias,
                tas.target_tag_id AS target_tag_id,
                t.name AS target_tag_name,
                tas.score AS score,
                tas.source AS source,
                tas.reason AS reason,
                tas.status AS status,
                tas.hit_count AS hit_count,
                tas.first_seen_epoch AS first_seen_epoch,
                tas.last_seen_epoch AS last_seen_epoch
            FROM tag_alias_suggestions tas
            JOIN tags t ON t.id = tas.target_tag_id
            WHERE tas.status = 'pending'
            ORDER BY tas.hit_count DESC, tas.score DESC, tas.last_seen_epoch DESC
            """
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "alias": str(row["alias"] or ""),
                "target_tag_id": int(row["target_tag_id"] or 0),
                "target_tag_name": str(row["target_tag_name"] or ""),
                "score": float(row["score"] or 0.0),
                "source": str(row["source"] or ""),
                "reason": str(row["reason"] or ""),
                "status": str(row["status"] or "pending"),
                "hit_count": int(row["hit_count"] or 0),
                "first_seen_epoch": int(row["first_seen_epoch"] or 0),
                "last_seen_epoch": int(row["last_seen_epoch"] or 0),
            }
            for row in rows
        ]

    def approve_tag_alias_suggestions(self, suggestion_ids: list[int]) -> Dict[str, int]:
        conn = self._require_conn()
        unique_ids = sorted({int(item) for item in suggestion_ids if int(item) > 0})
        if not unique_ids:
            return {"approved_suggestions": 0, "alias_memory_written": 0}

        placeholders = ", ".join(["?"] * len(unique_ids))
        now = _now_epoch()
        approved = 0
        alias_memory_written = 0
        with conn:
            rows = conn.execute(
                f"""
                SELECT id, alias, target_tag_id
                FROM tag_alias_suggestions
                WHERE id IN ({placeholders}) AND status = 'pending'
                """,
                tuple(unique_ids),
            ).fetchall()
            for row in rows:
                suggestion_id = int(row["id"])
                alias = str(row["alias"] or "").strip()
                tag_id = int(row["target_tag_id"] or 0)
                if alias and tag_id > 0:
                    created = self._upsert_tag_alias_row(
                        conn=conn,
                        alias=alias,
                        tag_id=tag_id,
                        confidence=0.9,
                        source="suggestion_approved",
                        status="verified",
                        now=now,
                    )
                    if created:
                        alias_memory_written += 1
                conn.execute(
                    """
                    UPDATE tag_alias_suggestions
                    SET status = 'approved', last_seen_epoch = ?, updated_at_epoch = ?
                    WHERE id = ?
                    """,
                    (now, now, suggestion_id),
                )
                approved += 1

            if approved > 0:
                self._set_meta(conn, "updated_at", str(now))
        return {
            "approved_suggestions": approved,
            "alias_memory_written": alias_memory_written,
        }

    def reject_tag_alias_suggestions(self, suggestion_ids: list[int]) -> int:
        conn = self._require_conn()
        unique_ids = sorted({int(item) for item in suggestion_ids if int(item) > 0})
        if not unique_ids:
            return 0

        placeholders = ", ".join(["?"] * len(unique_ids))
        now = _now_epoch()
        with conn:
            cur = conn.execute(
                f"""
                UPDATE tag_alias_suggestions
                SET status = 'rejected', last_seen_epoch = ?, updated_at_epoch = ?
                WHERE id IN ({placeholders})
                  AND status = 'pending'
                """,
                (now, now, *tuple(unique_ids)),
            )
            affected = int(cur.rowcount or 0)
            if affected > 0:
                self._set_meta(conn, "updated_at", str(now))
        return affected

    def upsert_tags(self, names: list[str]) -> int:
        conn = self._require_conn()
        clean = self._normalize_tag_names(names)
        if not clean:
            return 0

        now = _now_epoch()
        created = 0
        with conn:
            for name in clean:
                row = conn.execute(
                    "SELECT id FROM tags WHERE name = ?",
                    (name,),
                ).fetchone()
                if row is not None:
                    continue
                conn.execute("INSERT INTO tags(name) VALUES (?)", (name,))
                created += 1
            if created > 0:
                self._set_meta(conn, "updated_at", str(now))

        if created > 0:
            self._load_data()
        return created

    def delete_tags_by_ids(self, tag_ids: list[int]) -> int:
        conn = self._require_conn()
        unique_ids = sorted({int(tag_id) for tag_id in tag_ids if int(tag_id) > 0})
        if not unique_ids:
            return 0

        placeholders = ", ".join(["?"] * len(unique_ids))
        now = _now_epoch()
        with conn:
            cur = conn.execute(
                f"DELETE FROM tags WHERE id IN ({placeholders})",
                tuple(unique_ids),
            )
            removed = int(cur.rowcount or 0)
            if removed > 0:
                self._set_meta(conn, "updated_at", str(now))

        if removed > 0:
            self._load_data()
        return removed

    def add_manual_tag_to_video(self, video_id: str, tag_name: str) -> bool:
        conn = self._require_conn()
        clean = self._normalize_tag_names([tag_name])
        if not clean:
            return False
        name = clean[0]

        row = conn.execute(
            "SELECT 1 FROM videos WHERE id = ?",
            (video_id,),
        ).fetchone()
        if row is None:
            return False

        now = _now_epoch()
        with conn:
            conn.execute(
                "INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING",
                (name,),
            )
            tag_row = conn.execute(
                "SELECT id FROM tags WHERE name = ?",
                (name,),
            ).fetchone()
            if tag_row is None:
                return False
            tag_id = int(tag_row["id"])
            conn.execute(
                """
                INSERT INTO video_tags(video_id, tag_id, source, confidence, created_at_epoch, updated_at_epoch)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id, tag_id, source) DO UPDATE SET
                    confidence = excluded.confidence,
                    updated_at_epoch = excluded.updated_at_epoch
                """,
                (video_id, tag_id, "manual", None, now, now),
            )
            self._set_meta(conn, "updated_at", str(now))

        self._load_data()
        return True

    def remove_tag_from_video(self, video_id: str, tag_name: str) -> int:
        conn = self._require_conn()
        clean = self._normalize_tag_names([tag_name])
        if not clean:
            return 0
        name = clean[0]
        tag_row = conn.execute(
            "SELECT id FROM tags WHERE name = ?",
            (name,),
        ).fetchone()
        if tag_row is None:
            return 0
        tag_id = int(tag_row["id"])

        now = _now_epoch()
        with conn:
            cur = conn.execute(
                "DELETE FROM video_tags WHERE video_id = ? AND tag_id = ?",
                (video_id, tag_id),
            )
            removed = int(cur.rowcount or 0)
            if removed > 0:
                self._set_meta(conn, "updated_at", str(now))

        if removed > 0:
            self._load_data()
        return removed

    def _upsert_video_tags(
        self,
        conn: sqlite3.Connection,
        video_id: str,
        tags: list[Any],
        now_epoch: int,
    ) -> None:
        clean_tags = []
        seen = set()
        for tag in tags:
            name = str(tag).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            clean_tags.append(name)

        conn.execute(
            "DELETE FROM video_tags WHERE video_id = ? AND source = 'manual'",
            (video_id,),
        )
        for tag_name in clean_tags:
            conn.execute(
                "INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING",
                (tag_name,),
            )
            row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
            if row is None:
                continue
            tag_id = int(row["id"])
            conn.execute(
                """
                INSERT INTO video_tags(video_id, tag_id, source, confidence, created_at_epoch, updated_at_epoch)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id, tag_id, source) DO UPDATE SET
                    confidence = excluded.confidence,
                    updated_at_epoch = excluded.updated_at_epoch
                """,
                (video_id, tag_id, "manual", None, now_epoch, now_epoch),
            )

    def _upsert_tag_alias_row(
        self,
        conn: sqlite3.Connection,
        alias: str,
        tag_id: int,
        confidence: float,
        source: str,
        status: str,
        now: int,
    ) -> bool:
        clean_alias = str(alias or "").strip()
        if len(clean_alias) < 2:
            return False
        safe_status = str(status or "verified").strip().lower() or "verified"
        if safe_status not in {"verified", "auto_pending", "disabled"}:
            safe_status = "verified"
        safe_source = str(source or "manual").strip() or "manual"

        row = conn.execute(
            "SELECT id, hit_count FROM tag_alias_memory WHERE alias = ? AND tag_id = ?",
            (clean_alias, int(tag_id)),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO tag_alias_memory(
                    alias, tag_id, confidence, status, source, hit_count,
                    first_mapped_epoch, last_mapped_epoch, created_at_epoch, updated_at_epoch
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    clean_alias,
                    int(tag_id),
                    float(confidence),
                    safe_status,
                    safe_source,
                    int(now),
                    int(now),
                    int(now),
                    int(now),
                ),
            )
            return True

        alias_id = int(row["id"])
        hit_count = int(row["hit_count"] or 0) + 1
        conn.execute(
            """
            UPDATE tag_alias_memory
            SET confidence = ?, status = ?, source = ?, hit_count = ?, last_mapped_epoch = ?, updated_at_epoch = ?
            WHERE id = ?
            """,
            (
                float(confidence),
                safe_status,
                safe_source,
                hit_count,
                int(now),
                int(now),
                alias_id,
            ),
        )
        return False

    def _prepare_blacklist_keys(self, terms: list[str]) -> list[str]:
        keys = sorted(
            {
                _normalize_lookup_key(term)
                for term in terms
                if len(_normalize_lookup_key(term)) >= 2
            },
            key=len,
            reverse=True,
        )
        return keys

    def _matches_blacklist_term(self, term: str, blacklist_keys: list[str]) -> bool:
        lookup = _normalize_lookup_key(term)
        if len(lookup) < 2:
            return False
        for blocked in blacklist_keys:
            if blocked and blocked in lookup:
                return True
        return False

    def _upsert_blacklist_term_row(
        self,
        conn: sqlite3.Connection,
        term: str,
        source: str,
        reason: str,
        now: int,
    ) -> bool:
        clean_term = str(term or "").strip()
        if len(clean_term) < 2:
            return False
        safe_source = str(source or "manual").strip() or "manual"
        safe_reason = str(reason or "").strip()
        row = conn.execute(
            "SELECT id, hit_count FROM tag_blacklist WHERE term = ?",
            (clean_term,),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO tag_blacklist(
                    term, source, reason, hit_count,
                    first_seen_epoch, last_seen_epoch, created_at_epoch, updated_at_epoch
                )
                VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    clean_term,
                    safe_source,
                    safe_reason,
                    int(now),
                    int(now),
                    int(now),
                    int(now),
                ),
            )
            return True

        blacklist_id = int(row["id"])
        hit_count = int(row["hit_count"] or 0) + 1
        conn.execute(
            """
            UPDATE tag_blacklist
            SET source = ?, reason = ?, hit_count = ?, last_seen_epoch = ?, updated_at_epoch = ?
            WHERE id = ?
            """,
            (
                safe_source,
                safe_reason,
                hit_count,
                int(now),
                int(now),
                blacklist_id,
            ),
        )
        return False

    def _normalize_tag_names(self, names: list[Any]) -> list[str]:
        out: list[str] = []
        seen = set()
        for raw in names:
            name = str(raw).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
        return out

    def _load_data(self) -> None:
        conn = self._require_conn()
        meta_rows = conn.execute("SELECT key, value FROM meta").fetchall()
        meta = {str(row["key"]): str(row["value"]) for row in meta_rows}

        videos_rows = conn.execute(
            """
            SELECT
                videos.id, videos.rel_path, videos.filename, videos.ext, videos.size_bytes, videos.mtime_epoch,
                videos.added_at_epoch, videos.last_seen_epoch, videos.missing, videos.title_guess, videos.status, videos.notes,
                videos.title_tag_mined_epoch AS title_tag_mined_epoch,
                vm.duration_ms AS duration_ms,
                vm.width AS width,
                vm.height AS height,
                vm.fps AS fps,
                vm.video_codec AS video_codec,
                vm.audio_codec AS audio_codec,
                vm.bitrate_kbps AS bitrate_kbps,
                vm.audio_channels AS audio_channels,
                vm.media_created_epoch AS media_created_epoch,
                vm.probe_status AS probe_status,
                vm.probe_error AS probe_error,
                th.thumb_rel_path AS thumb_rel_path,
                th.status AS thumb_status,
                th.error_msg AS thumb_error,
                th.generated_epoch AS thumb_generated_epoch,
                th.frame_ms AS thumb_frame_ms
            FROM videos
            LEFT JOIN video_media vm ON vm.video_id = videos.id
            LEFT JOIN thumbnails th ON th.video_id = videos.id
            ORDER BY filename COLLATE NOCASE
            """
        ).fetchall()

        tag_rows = conn.execute(
            """
            SELECT vt.video_id AS video_id, t.name AS tag_name
            FROM video_tags vt
            JOIN tags t ON t.id = vt.tag_id
            WHERE vt.source IN ('manual', 'ai_title')
            ORDER BY
                CASE vt.source WHEN 'manual' THEN 0 ELSE 1 END,
                t.name COLLATE NOCASE
            """
        ).fetchall()
        tag_map: Dict[str, list[str]] = {}
        for row in tag_rows:
            vid = str(row["video_id"])
            tag_name = str(row["tag_name"])
            tag_map.setdefault(vid, [])
            if tag_name not in tag_map[vid]:
                tag_map[vid].append(tag_name)

        videos: Dict[str, Dict[str, Any]] = {}
        for row in videos_rows:
            vid = str(row["id"])
            videos[vid] = {
                "id": vid,
                "rel_path": str(row["rel_path"]),
                "filename": str(row["filename"]),
                "ext": str(row["ext"]),
                "size_bytes": int(row["size_bytes"] or 0),
                "mtime_epoch": int(row["mtime_epoch"] or 0),
                "added_at_epoch": int(row["added_at_epoch"] or 0),
                "last_seen_epoch": int(row["last_seen_epoch"] or 0),
                "missing": bool(int(row["missing"] or 0)),
                "title_guess": str(row["title_guess"] or ""),
                "tags": tag_map.get(vid, []),
                "status": str(row["status"] or ""),
                "notes": str(row["notes"] or ""),
                "title_tag_mined_epoch": int(row["title_tag_mined_epoch"] or 0),
                "duration_ms": int(row["duration_ms"] or 0),
                "width": int(row["width"] or 0),
                "height": int(row["height"] or 0),
                "fps": float(row["fps"] or 0.0),
                "video_codec": str(row["video_codec"] or ""),
                "audio_codec": str(row["audio_codec"] or ""),
                "bitrate_kbps": int(row["bitrate_kbps"] or 0),
                "audio_channels": int(row["audio_channels"] or 0),
                "media_created_epoch": int(row["media_created_epoch"] or 0),
                "thumb_rel_path": str(row["thumb_rel_path"] or ""),
                "probe_status": str(row["probe_status"] or ""),
                "probe_error": str(row["probe_error"] or ""),
                "thumb_status": str(row["thumb_status"] or ""),
                "thumb_error": str(row["thumb_error"] or ""),
                "thumb_generated_epoch": int(row["thumb_generated_epoch"] or 0),
                "thumb_frame_ms": int(row["thumb_frame_ms"] or 0),
            }

        self._data = {
            "version": int(meta.get("version", str(DB_VERSION))),
            "root_id": meta.get("root_id", ""),
            "created_at": int(meta.get("created_at", "0") or 0),
            "updated_at": int(meta.get("updated_at", "0") or 0),
            "videos": videos,
        }

    def _bootstrap_meta(self) -> None:
        conn = self._require_conn()
        now = _now_epoch()
        existing = {
            str(row["key"]): str(row["value"])
            for row in conn.execute("SELECT key, value FROM meta").fetchall()
        }
        with conn:
            if "version" not in existing:
                self._set_meta(conn, "version", str(DB_VERSION))
            if "root_id" not in existing:
                self._set_meta(conn, "root_id", str(uuid.uuid4()))
            if "created_at" not in existing:
                self._set_meta(conn, "created_at", str(now))
            if "updated_at" not in existing:
                self._set_meta(conn, "updated_at", str(now))

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO meta(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def _create_schema(self) -> None:
        conn = self._require_conn()
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    rel_path TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    ext TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mtime_epoch INTEGER NOT NULL,
                    added_at_epoch INTEGER NOT NULL,
                    last_seen_epoch INTEGER NOT NULL,
                    missing INTEGER NOT NULL DEFAULT 0,
                    missing_since_epoch INTEGER,
                    title_guess TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    title_tag_mined_epoch INTEGER NOT NULL DEFAULT 0,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS video_media (
                    video_id TEXT PRIMARY KEY,
                    duration_ms INTEGER,
                    width INTEGER,
                    height INTEGER,
                    fps REAL,
                    video_codec TEXT,
                    audio_codec TEXT,
                    bitrate_kbps INTEGER,
                    audio_channels INTEGER,
                    media_created_epoch INTEGER,
                    probe_epoch INTEGER,
                    probe_status TEXT,
                    probe_error TEXT,
                    extra_json TEXT,
                    FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS thumbnails (
                    video_id TEXT PRIMARY KEY,
                    thumb_rel_path TEXT,
                    width INTEGER,
                    height INTEGER,
                    frame_ms INTEGER,
                    source_mtime_epoch INTEGER,
                    generated_epoch INTEGER,
                    generator TEXT,
                    status TEXT,
                    error_msg TEXT,
                    FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    color TEXT,
                    description TEXT
                );

                CREATE TABLE IF NOT EXISTS video_tags (
                    video_id TEXT NOT NULL,
                    tag_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    PRIMARY KEY(video_id, tag_id, source),
                    FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE,
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS concepts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    status TEXT NOT NULL DEFAULT 'active',
                    source TEXT NOT NULL DEFAULT 'manual',
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS concept_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_id INTEGER NOT NULL,
                    alias TEXT NOT NULL COLLATE NOCASE,
                    confidence REAL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    UNIQUE(concept_id, alias),
                    FOREIGN KEY(concept_id) REFERENCES concepts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS concept_tag_links (
                    concept_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    relation TEXT NOT NULL DEFAULT 'primary',
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    PRIMARY KEY(concept_id, tag_id),
                    FOREIGN KEY(concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tag_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    mapped_tag_id INTEGER,
                    first_seen_epoch INTEGER NOT NULL,
                    last_seen_epoch INTEGER NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(mapped_tag_id) REFERENCES tags(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS tag_candidate_hits (
                    candidate_id INTEGER NOT NULL,
                    video_id TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    PRIMARY KEY(candidate_id, video_id),
                    FOREIGN KEY(candidate_id) REFERENCES tag_candidates(id) ON DELETE CASCADE,
                    FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tag_blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    source TEXT NOT NULL DEFAULT 'manual',
                    reason TEXT NOT NULL DEFAULT '',
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    first_seen_epoch INTEGER NOT NULL,
                    last_seen_epoch INTEGER NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tag_alias_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT NOT NULL COLLATE NOCASE,
                    tag_id INTEGER NOT NULL,
                    confidence REAL,
                    status TEXT NOT NULL DEFAULT 'verified',
                    source TEXT NOT NULL DEFAULT 'manual',
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    first_mapped_epoch INTEGER NOT NULL,
                    last_mapped_epoch INTEGER NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    UNIQUE(alias, tag_id),
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tag_alias_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT NOT NULL COLLATE NOCASE,
                    target_tag_id INTEGER NOT NULL,
                    score REAL,
                    source TEXT NOT NULL DEFAULT 'model',
                    reason TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    first_seen_epoch INTEGER NOT NULL,
                    last_seen_epoch INTEGER NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    UNIQUE(alias, target_tag_id, status),
                    FOREIGN KEY(target_tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS saved_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    filter_json TEXT NOT NULL,
                    sort_json TEXT NOT NULL,
                    columns_json TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_videos_filename ON videos(filename);
                CREATE INDEX IF NOT EXISTS idx_videos_mtime ON videos(mtime_epoch);
                CREATE INDEX IF NOT EXISTS idx_videos_missing_seen ON videos(missing, last_seen_epoch);
                CREATE INDEX IF NOT EXISTS idx_video_media_duration ON video_media(duration_ms);
                CREATE INDEX IF NOT EXISTS idx_video_media_resolution ON video_media(width, height);
                CREATE INDEX IF NOT EXISTS idx_video_tags_tag_source ON video_tags(tag_id, source);
                CREATE INDEX IF NOT EXISTS idx_thumbnails_status_epoch ON thumbnails(status, generated_epoch);
                CREATE INDEX IF NOT EXISTS idx_concepts_status_name ON concepts(status, name);
                CREATE INDEX IF NOT EXISTS idx_concept_aliases_alias ON concept_aliases(alias);
                CREATE INDEX IF NOT EXISTS idx_concept_aliases_concept ON concept_aliases(concept_id);
                CREATE INDEX IF NOT EXISTS idx_concept_tag_links_tag ON concept_tag_links(tag_id);
                CREATE INDEX IF NOT EXISTS idx_tag_candidates_status_seen ON tag_candidates(status, last_seen_epoch);
                CREATE INDEX IF NOT EXISTS idx_tag_candidate_hits_video ON tag_candidate_hits(video_id);
                CREATE INDEX IF NOT EXISTS idx_tag_blacklist_term ON tag_blacklist(term);
                CREATE INDEX IF NOT EXISTS idx_tag_alias_memory_alias ON tag_alias_memory(alias);
                CREATE INDEX IF NOT EXISTS idx_tag_alias_memory_tag_status ON tag_alias_memory(tag_id, status);
                CREATE INDEX IF NOT EXISTS idx_tag_alias_suggestions_status_seen ON tag_alias_suggestions(status, last_seen_epoch);
                CREATE INDEX IF NOT EXISTS idx_tag_alias_suggestions_target ON tag_alias_suggestions(target_tag_id);
                """
            )

    def _migrate_schema(self) -> None:
        conn = self._require_conn()
        vm_cols = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(video_media)").fetchall()
        }
        video_cols = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(videos)").fetchall()
        }
        tag_candidate_cols = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(tag_candidates)").fetchall()
        }
        with conn:
            if "media_created_epoch" not in vm_cols:
                conn.execute("ALTER TABLE video_media ADD COLUMN media_created_epoch INTEGER")
            if "probe_error" not in vm_cols:
                conn.execute("ALTER TABLE video_media ADD COLUMN probe_error TEXT")
            if "title_tag_mined_epoch" not in video_cols:
                conn.execute(
                    "ALTER TABLE videos ADD COLUMN title_tag_mined_epoch INTEGER NOT NULL DEFAULT 0"
                )
            if "mapped_tag_id" not in tag_candidate_cols:
                conn.execute("ALTER TABLE tag_candidates ADD COLUMN mapped_tag_id INTEGER")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tag_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    mapped_tag_id INTEGER,
                    first_seen_epoch INTEGER NOT NULL,
                    last_seen_epoch INTEGER NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(mapped_tag_id) REFERENCES tags(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS tag_candidate_hits (
                    candidate_id INTEGER NOT NULL,
                    video_id TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    PRIMARY KEY(candidate_id, video_id),
                    FOREIGN KEY(candidate_id) REFERENCES tag_candidates(id) ON DELETE CASCADE,
                    FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tag_blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    source TEXT NOT NULL DEFAULT 'manual',
                    reason TEXT NOT NULL DEFAULT '',
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    first_seen_epoch INTEGER NOT NULL,
                    last_seen_epoch INTEGER NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tag_candidates_status_seen
                    ON tag_candidates(status, last_seen_epoch);
                CREATE INDEX IF NOT EXISTS idx_tag_candidates_mapped_tag
                    ON tag_candidates(mapped_tag_id);
                CREATE INDEX IF NOT EXISTS idx_tag_candidate_hits_video
                    ON tag_candidate_hits(video_id);
                CREATE INDEX IF NOT EXISTS idx_tag_blacklist_term
                    ON tag_blacklist(term);

                CREATE TABLE IF NOT EXISTS tag_alias_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT NOT NULL COLLATE NOCASE,
                    tag_id INTEGER NOT NULL,
                    confidence REAL,
                    status TEXT NOT NULL DEFAULT 'verified',
                    source TEXT NOT NULL DEFAULT 'manual',
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    first_mapped_epoch INTEGER NOT NULL,
                    last_mapped_epoch INTEGER NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    UNIQUE(alias, tag_id),
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tag_alias_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT NOT NULL COLLATE NOCASE,
                    target_tag_id INTEGER NOT NULL,
                    score REAL,
                    source TEXT NOT NULL DEFAULT 'model',
                    reason TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    first_seen_epoch INTEGER NOT NULL,
                    last_seen_epoch INTEGER NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    UNIQUE(alias, target_tag_id, status),
                    FOREIGN KEY(target_tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tag_alias_memory_alias
                    ON tag_alias_memory(alias);
                CREATE INDEX IF NOT EXISTS idx_tag_alias_memory_tag_status
                    ON tag_alias_memory(tag_id, status);
                CREATE INDEX IF NOT EXISTS idx_tag_alias_suggestions_status_seen
                    ON tag_alias_suggestions(status, last_seen_epoch);
                CREATE INDEX IF NOT EXISTS idx_tag_alias_suggestions_target
                    ON tag_alias_suggestions(target_tag_id);

                CREATE TABLE IF NOT EXISTS concepts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    status TEXT NOT NULL DEFAULT 'active',
                    source TEXT NOT NULL DEFAULT 'manual',
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS concept_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_id INTEGER NOT NULL,
                    alias TEXT NOT NULL COLLATE NOCASE,
                    confidence REAL,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    UNIQUE(concept_id, alias),
                    FOREIGN KEY(concept_id) REFERENCES concepts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS concept_tag_links (
                    concept_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    relation TEXT NOT NULL DEFAULT 'primary',
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    PRIMARY KEY(concept_id, tag_id),
                    FOREIGN KEY(concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_concepts_status_name
                    ON concepts(status, name);
                CREATE INDEX IF NOT EXISTS idx_concept_aliases_alias
                    ON concept_aliases(alias);
                CREATE INDEX IF NOT EXISTS idx_concept_aliases_concept
                    ON concept_aliases(concept_id);
                CREATE INDEX IF NOT EXISTS idx_concept_tag_links_tag
                    ON concept_tag_links(tag_id);
                """
            )
            conn.execute(
                """
                UPDATE tag_candidates
                SET status = 'blacklisted'
                WHERE status = 'rejected'
                """
            )
            self._set_meta(conn, "version", str(DB_VERSION))

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLite repository is not initialized")
        return self._conn
