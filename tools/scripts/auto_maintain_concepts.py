from __future__ import annotations

import argparse
import re
import sqlite3
import time
import unicodedata
from pathlib import Path
from typing import Dict, Iterable


LIB_DIRNAME = ".mm"
DB_FILENAME = "library.db"

CONCEPT_HIGH_SCHOOL_STAGE = "\u9ad8\u4e2d\u9636\u6bb5"
CONCEPT_JUNIOR_STAGE = "\u521d\u4e2d\u9636\u6bb5"
CONCEPT_YOUNG = "\u7a1a\u5ae9\u672a\u6210\u5e74"


def _now_epoch() -> int:
    return int(time.time())


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().lower()


def _canonical_grade(token: str) -> str:
    value = (token or "").strip()
    if not value:
        return ""
    value = (
        value.replace("1", "\u4e00")
        .replace("2", "\u4e8c")
        .replace("3", "\u4e09")
        .replace("\u9ad81", "\u9ad8\u4e00")
        .replace("\u9ad82", "\u9ad8\u4e8c")
        .replace("\u9ad83", "\u9ad8\u4e09")
        .replace("\u521d1", "\u521d\u4e00")
        .replace("\u521d2", "\u521d\u4e8c")
        .replace("\u521d3", "\u521d\u4e09")
    )
    return value


def _decode_display(text: str) -> str:
    return str(text or "").encode("unicode_escape").decode("ascii")


def ensure_concept_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
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


def fetch_tags(conn: sqlite3.Connection) -> Dict[str, int]:
    rows = conn.execute("SELECT id, name FROM tags").fetchall()
    out: Dict[str, int] = {}
    for row in rows:
        tag_id = int(row[0])
        name = str(row[1] or "").strip()
        if not name:
            continue
        out[name] = tag_id
    return out


def upsert_concept(
    conn: sqlite3.Connection,
    name: str,
    source: str,
    now: int,
) -> tuple[int, bool]:
    row = conn.execute("SELECT id FROM concepts WHERE name = ?", (name,)).fetchone()
    if row is not None:
        concept_id = int(row[0])
        conn.execute(
            """
            UPDATE concepts
            SET status = 'active', source = ?, updated_at_epoch = ?
            WHERE id = ?
            """,
            (source, now, concept_id),
        )
        return concept_id, False

    cur = conn.execute(
        """
        INSERT INTO concepts(name, status, source, created_at_epoch, updated_at_epoch)
        VALUES (?, 'active', ?, ?, ?)
        """,
        (name, source, now, now),
    )
    return int(cur.lastrowid or 0), True


def upsert_concept_alias(
    conn: sqlite3.Connection,
    concept_id: int,
    alias: str,
    confidence: float,
    now: int,
) -> bool:
    clean = str(alias or "").strip()
    if len(clean) < 2:
        return False

    row = conn.execute(
        "SELECT id FROM concept_aliases WHERE concept_id = ? AND alias = ?",
        (concept_id, clean),
    ).fetchone()
    if row is not None:
        conn.execute(
            """
            UPDATE concept_aliases
            SET confidence = ?, updated_at_epoch = ?
            WHERE id = ?
            """,
            (float(confidence), now, int(row[0])),
        )
        return False

    conn.execute(
        """
        INSERT INTO concept_aliases(concept_id, alias, confidence, created_at_epoch, updated_at_epoch)
        VALUES (?, ?, ?, ?, ?)
        """,
        (concept_id, clean, float(confidence), now, now),
    )
    return True


def upsert_concept_tag_link(
    conn: sqlite3.Connection,
    concept_id: int,
    tag_id: int,
    weight: float,
    relation: str,
    now: int,
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM concept_tag_links WHERE concept_id = ? AND tag_id = ?",
        (concept_id, tag_id),
    ).fetchone()
    if row is not None:
        conn.execute(
            """
            UPDATE concept_tag_links
            SET weight = ?, relation = ?, updated_at_epoch = ?
            WHERE concept_id = ? AND tag_id = ?
            """,
            (float(weight), relation, now, concept_id, tag_id),
        )
        return False

    conn.execute(
        """
        INSERT INTO concept_tag_links(
            concept_id, tag_id, weight, relation, created_at_epoch, updated_at_epoch
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (concept_id, tag_id, float(weight), relation, now, now),
    )
    return True


def seed_tag_concepts(
    conn: sqlite3.Connection,
    tags: Dict[str, int],
    now: int,
) -> tuple[int, int, int]:
    created_concepts = 0
    created_aliases = 0
    created_links = 0

    for tag_name, tag_id in tags.items():
        concept_id, created = upsert_concept(
            conn=conn,
            name=tag_name,
            source="auto_seed_tag",
            now=now,
        )
        if created:
            created_concepts += 1
        if upsert_concept_alias(conn, concept_id, tag_name, confidence=1.0, now=now):
            created_aliases += 1
        if upsert_concept_tag_link(
            conn,
            concept_id,
            tag_id,
            weight=1.0,
            relation="primary",
            now=now,
        ):
            created_links += 1
    return created_concepts, created_aliases, created_links


def _existing_tag_ids(tags: Dict[str, int], names: Iterable[str]) -> list[int]:
    out: list[int] = []
    for name in names:
        tag_id = tags.get(name)
        if tag_id is not None and tag_id not in out:
            out.append(tag_id)
    return out


def seed_stage_concepts(
    conn: sqlite3.Connection,
    tags: Dict[str, int],
    now: int,
) -> tuple[Dict[str, int], int, int, int]:
    created_concepts = 0
    created_aliases = 0
    created_links = 0

    plans = [
        {
            "name": CONCEPT_HIGH_SCHOOL_STAGE,
            "source": "auto_stage",
            "tags": [
                "\u9ad8\u4e2d",
                "\u9ad8\u4e2d\u751f",
                "\u4e2d\u5b66\u751f",
            ],
            "aliases": [
                "\u9ad8\u4e00",
                "\u9ad8\u4e8c",
                "\u9ad8\u4e09",
                "\u9ad8\u4e2d\u751f",
                "\u9ad8\u4e2d\u59b9",
                "\u9ad8\u4e2d\u5973",
            ],
            "relation": "semantic_cluster",
            "weight": 0.95,
        },
        {
            "name": CONCEPT_JUNIOR_STAGE,
            "source": "auto_stage",
            "tags": [
                "\u521d\u4e2d",
                "\u4e2d\u5b66\u751f",
            ],
            "aliases": [
                "\u521d\u4e00",
                "\u521d\u4e8c",
                "\u521d\u4e09",
                "\u521d\u4e2d\u751f",
                "\u4e2d\u5b66\u751f",
            ],
            "relation": "semantic_cluster",
            "weight": 0.95,
        },
        {
            "name": CONCEPT_YOUNG,
            "source": "auto_stage",
            "tags": [
                "\u7a1a\u5ae9",
                "\u5ae9",
                "\u5c0f\u5973\u5b69",
                "\u5c11\u5973",
                "\u841d\u8389",
                "\u4e2d\u5b66\u751f",
                "\u9ad8\u4e2d\u751f",
            ],
            "aliases": [
                "\u672a\u6210\u5e74",
                "\u7a1a\u5ae9",
                "\u5e7c\u6001",
                "15\u5c81",
                "16\u5c81",
                "17\u5c81",
                "18\u5c81",
            ],
            "relation": "semantic_cluster",
            "weight": 0.9,
        },
    ]

    concept_ids: Dict[str, int] = {}
    for plan in plans:
        tag_ids = _existing_tag_ids(tags, plan["tags"])
        if not tag_ids:
            continue
        concept_id, created = upsert_concept(
            conn=conn,
            name=str(plan["name"]),
            source=str(plan["source"]),
            now=now,
        )
        if created:
            created_concepts += 1
        concept_ids[str(plan["name"])] = concept_id

        for alias in list(plan["aliases"]):
            if upsert_concept_alias(
                conn,
                concept_id,
                alias,
                confidence=0.9,
                now=now,
            ):
                created_aliases += 1

        for tag_id in tag_ids:
            if upsert_concept_tag_link(
                conn,
                concept_id,
                tag_id,
                weight=float(plan["weight"]),
                relation=str(plan["relation"]),
                now=now,
            ):
                created_links += 1
    return concept_ids, created_concepts, created_aliases, created_links


def mine_dynamic_aliases(
    conn: sqlite3.Connection,
    concept_ids: Dict[str, int],
    now: int,
) -> tuple[int, dict[str, int]]:
    rows = conn.execute(
        "SELECT filename, title_guess FROM videos WHERE COALESCE(missing, 0) = 0"
    ).fetchall()

    grade_re = re.compile(
        r"(\u9ad8[\u4e00\u4e8c\u4e09123]|\u521d[\u4e00\u4e8c\u4e09123]|\u9ad8\u4e2d\u751f?|\u521d\u4e2d\u751f?)"
    )
    age_re = re.compile(r"([1-9][0-9]?)\s*\u5c81")

    high_aliases: set[str] = set()
    junior_aliases: set[str] = set()
    young_aliases: set[str] = set()

    for row in rows:
        filename = str(row[0] or "")
        title_guess = str(row[1] or "")
        stem = Path(filename).stem
        text = _normalize_text(f"{title_guess} {stem}")
        if not text:
            continue

        for grade in grade_re.findall(text):
            token = _canonical_grade(grade)
            if not token:
                continue
            if token.startswith("\u9ad8"):
                high_aliases.add(token)
            if token.startswith("\u521d"):
                junior_aliases.add(token)
            if (
                "\u521d\u4e2d" in token
                or "\u9ad8\u4e2d" in token
                or "\u4e2d\u5b66\u751f" in token
            ):
                young_aliases.add(token)

        for match in age_re.finditer(text):
            try:
                age = int(match.group(1))
            except Exception:
                continue
            if 0 < age <= 18:
                young_aliases.add(f"{age}\u5c81")

    alias_created = 0
    stats = {
        "high_school_aliases": len(high_aliases),
        "junior_aliases": len(junior_aliases),
        "young_aliases": len(young_aliases),
    }

    high_id = concept_ids.get(CONCEPT_HIGH_SCHOOL_STAGE)
    junior_id = concept_ids.get(CONCEPT_JUNIOR_STAGE)
    young_id = concept_ids.get(CONCEPT_YOUNG)

    if high_id is not None:
        for alias in sorted(high_aliases):
            if upsert_concept_alias(conn, high_id, alias, confidence=0.88, now=now):
                alias_created += 1
    if junior_id is not None:
        for alias in sorted(junior_aliases):
            if upsert_concept_alias(conn, junior_id, alias, confidence=0.88, now=now):
                alias_created += 1
    if young_id is not None:
        for alias in sorted(young_aliases):
            if upsert_concept_alias(conn, young_id, alias, confidence=0.85, now=now):
                alias_created += 1

    return alias_created, stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto maintain concept tables from existing tags and video titles."
    )
    parser.add_argument(
        "--library-root",
        required=True,
        help="Library root path that contains .mm/library.db",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(str(args.library_root)).expanduser().resolve()
    db_path = root / LIB_DIRNAME / DB_FILENAME
    if not db_path.exists():
        raise FileNotFoundError(f"library.db not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")

    try:
        ensure_concept_schema(conn)
        tags = fetch_tags(conn)
        if not tags:
            print("No tags found. Skip concept maintenance.")
            return 0

        now = _now_epoch()
        with conn:
            seed_concepts, seed_aliases, seed_links = seed_tag_concepts(conn, tags, now)
            concept_ids, stage_concepts, stage_aliases, stage_links = seed_stage_concepts(
                conn, tags, now
            )
            dynamic_aliases, dynamic_stats = mine_dynamic_aliases(conn, concept_ids, now)

        concept_count = int(conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0])
        alias_count = int(conn.execute("SELECT COUNT(*) FROM concept_aliases").fetchone()[0])
        link_count = int(conn.execute("SELECT COUNT(*) FROM concept_tag_links").fetchone()[0])

        print("Concept maintenance completed")
        print(f"library_root={root}")
        print(f"seed_concepts_created={seed_concepts}")
        print(f"seed_aliases_created={seed_aliases}")
        print(f"seed_links_created={seed_links}")
        print(f"stage_concepts_created={stage_concepts}")
        print(f"stage_aliases_created={stage_aliases}")
        print(f"stage_links_created={stage_links}")
        print(f"dynamic_aliases_created={dynamic_aliases}")
        print(
            "dynamic_alias_sources="
            f"high_school={dynamic_stats.get('high_school_aliases', 0)},"
            f"junior={dynamic_stats.get('junior_aliases', 0)},"
            f"young={dynamic_stats.get('young_aliases', 0)}"
        )
        print(f"final_counts: concepts={concept_count}, aliases={alias_count}, links={link_count}")

        preview_rows = conn.execute(
            """
            SELECT c.name AS concept_name, GROUP_CONCAT(DISTINCT ca.alias) AS aliases
            FROM concepts c
            LEFT JOIN concept_aliases ca ON ca.concept_id = c.id
            WHERE c.status = 'active'
            GROUP BY c.id, c.name
            ORDER BY c.name COLLATE NOCASE
            LIMIT 8
            """
        ).fetchall()
        print("preview_concepts:")
        for row in preview_rows:
            concept_name = str(row["concept_name"] or "")
            aliases = str(row["aliases"] or "")
            print(f"  - {_decode_display(concept_name)} :: {_decode_display(aliases)}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
