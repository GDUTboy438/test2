from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_AUTO_APPLY = 0.80
_DEFAULT_PENDING_REVIEW = 0.60
_DEFAULT_RECALL_TOP_K = 12
_DEFAULT_RECALL_MIN_SCORE = 0.45

_LIBRARY_LEVEL_FILE = ".mm/tag_mining_thresholds.json"
_PROJECT_LEVEL_FILE = "tools/config/tag_mining_thresholds.json"


def _clamp_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _as_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(fallback)


def _as_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(fallback)


@dataclass(frozen=True)
class TagScoreThreshold:
    auto_apply: float = _DEFAULT_AUTO_APPLY
    pending_review: float = _DEFAULT_PENDING_REVIEW

    def normalized(self) -> "TagScoreThreshold":
        auto_apply = _clamp_unit(float(self.auto_apply))
        pending_review = _clamp_unit(float(self.pending_review))
        if pending_review > auto_apply:
            pending_review = auto_apply
        return TagScoreThreshold(auto_apply=auto_apply, pending_review=pending_review)


@dataclass(frozen=True)
class TagMiningThresholdConfig:
    source_path: str = ""
    warning: str = ""
    recall_top_k: int = _DEFAULT_RECALL_TOP_K
    recall_min_score: float = _DEFAULT_RECALL_MIN_SCORE
    defaults: TagScoreThreshold = field(default_factory=TagScoreThreshold)
    per_tag: Dict[str, TagScoreThreshold] = field(default_factory=dict)

    def threshold_for(self, tag_name: str) -> TagScoreThreshold:
        key = str(tag_name or "").strip().lower()
        if not key:
            return self.defaults
        specific = self.per_tag.get(key)
        if specific is not None:
            return specific
        return self.defaults

    def to_payload(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "warning": self.warning,
            "recall_top_k": self.recall_top_k,
            "recall_min_score": self.recall_min_score,
            "defaults": {
                "auto_apply": self.defaults.auto_apply,
                "pending_review": self.defaults.pending_review,
            },
            "per_tag_count": len(self.per_tag),
        }


def load_tag_mining_threshold_config(
    library_root: Optional[Path],
) -> TagMiningThresholdConfig:
    project_root = Path(__file__).resolve().parents[2]
    candidates: list[Path] = []
    if library_root is not None:
        candidates.append(library_root / _LIBRARY_LEVEL_FILE)
    candidates.append(project_root / _PROJECT_LEVEL_FILE)

    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            return _parse_config(payload, source_path=str(candidate))
        except Exception as exc:
            return TagMiningThresholdConfig(
                source_path=str(candidate),
                warning=f"阈值配置解析失败，已回退默认值: {exc}",
                recall_top_k=_DEFAULT_RECALL_TOP_K,
                recall_min_score=_DEFAULT_RECALL_MIN_SCORE,
                defaults=TagScoreThreshold(
                    auto_apply=_DEFAULT_AUTO_APPLY,
                    pending_review=_DEFAULT_PENDING_REVIEW,
                ).normalized(),
                per_tag={},
            )

    return TagMiningThresholdConfig(
        source_path="built-in-default",
        warning="未找到阈值配置文件，已使用内置默认值。",
        recall_top_k=_DEFAULT_RECALL_TOP_K,
        recall_min_score=_DEFAULT_RECALL_MIN_SCORE,
        defaults=TagScoreThreshold(
            auto_apply=_DEFAULT_AUTO_APPLY,
            pending_review=_DEFAULT_PENDING_REVIEW,
        ).normalized(),
        per_tag={},
    )


def _parse_config(payload: Dict[str, Any], source_path: str) -> TagMiningThresholdConfig:
    embedding = payload.get("embedding") if isinstance(payload, dict) else {}
    thresholds = payload.get("thresholds") if isinstance(payload, dict) else {}
    per_tag_raw = payload.get("per_tag") if isinstance(payload, dict) else {}

    if not isinstance(embedding, dict):
        embedding = {}
    if not isinstance(thresholds, dict):
        thresholds = {}
    if not isinstance(per_tag_raw, dict):
        per_tag_raw = {}

    recall_top_k = max(1, _as_int(embedding.get("recall_top_k"), _DEFAULT_RECALL_TOP_K))
    recall_min_score = _clamp_unit(
        _as_float(embedding.get("recall_min_score"), _DEFAULT_RECALL_MIN_SCORE)
    )

    default_threshold = TagScoreThreshold(
        auto_apply=_as_float(thresholds.get("auto_apply"), _DEFAULT_AUTO_APPLY),
        pending_review=_as_float(
            thresholds.get("pending_review"), _DEFAULT_PENDING_REVIEW
        ),
    ).normalized()

    per_tag: Dict[str, TagScoreThreshold] = {}
    for raw_tag, raw_cfg in per_tag_raw.items():
        tag_name = str(raw_tag or "").strip()
        if not tag_name:
            continue
        if not isinstance(raw_cfg, dict):
            continue
        parsed = TagScoreThreshold(
            auto_apply=_as_float(raw_cfg.get("auto_apply"), default_threshold.auto_apply),
            pending_review=_as_float(
                raw_cfg.get("pending_review"), default_threshold.pending_review
            ),
        ).normalized()
        per_tag[tag_name.lower()] = parsed

    return TagMiningThresholdConfig(
        source_path=source_path,
        warning="",
        recall_top_k=recall_top_k,
        recall_min_score=recall_min_score,
        defaults=default_threshold,
        per_tag=per_tag,
    )
