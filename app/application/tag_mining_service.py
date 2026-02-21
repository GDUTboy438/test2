from __future__ import annotations

import math
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from app.application.models import TagMiningProgress, TagMiningResult
from app.application.ports import (
    EmbeddingModelPort,
    LibraryRepositoryPort,
    RerankerModelPort,
    TagGeneratorPort,
    TagMiningLoggerPort,
    TagMiningProgressCallback,
    TokenizerPort,
)
from app.infrastructure.tag_mining_thresholds import (
    TagMiningThresholdConfig,
    load_tag_mining_threshold_config,
)


_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]+")
_ALNUM_RE = re.compile(r"[a-z0-9]+")
_AGE_TERM_RE = re.compile(r"([1-9][0-9]?)\s*岁")
_GRADE_TERM_RE = re.compile(r"(?:高[一二三123]|初[一二三123])")
_MIXED_ID_RE = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z0-9]{8,}$")
_HEX_ID_RE = re.compile(r"^[0-9a-f]{8,}$")

# 业务过滤词改由数据库黑名单维护，代码层不再维护硬编码词表。
_STOP_TERMS: set[str] = set()


def _now_epoch() -> int:
    return int(time.time())


class _TagMiningCancelled(Exception):
    def __init__(self, phase: str, rel_path: str = "", processed: int = 0) -> None:
        super().__init__("标签提取已取消")
        self.phase = phase
        self.rel_path = rel_path
        self.processed = processed


class TitleTagMiningService:
    def __init__(
        self,
        repository: LibraryRepositoryPort,
        logger: TagMiningLoggerPort,
        embedding_model: Optional[EmbeddingModelPort] = None,
        reranker_model: Optional[RerankerModelPort] = None,
        tag_generator_model: Optional[TagGeneratorPort] = None,
        tokenizer: Optional[TokenizerPort] = None,
    ) -> None:
        self._repo = repository
        self._logger = logger
        self._embedding_model = embedding_model
        self._reranker_model = reranker_model
        self._tag_generator_model = tag_generator_model
        self._tokenizer = tokenizer

    def mine(
        self,
        progress: Optional[TagMiningProgressCallback] = None,
        min_df: int = 2,
        max_tags_per_video: int = 8,
        max_terms: int = 400,
        should_stop: Optional[Callable[[], bool]] = None,
        strategy: str = "auto",
        scope: str = "all",
    ) -> TagMiningResult:
        started = time.time()
        root = self._repo.root_path()
        if root is None:
            raise RuntimeError("未选择视频库根目录")

        min_df = max(1, int(min_df))
        max_tags_per_video = max(1, int(max_tags_per_video))
        max_terms = max(1, int(max_terms))
        scope_normalized = self._normalize_scope(scope)
        threshold_config = load_tag_mining_threshold_config(root)

        tokenizer_name = ""
        tokenizer_available = False
        tokenizer_reason = ""
        if self._tokenizer is None:
            tokenizer_reason = "未配置分词器"
        else:
            try:
                tokenizer_available = bool(self._tokenizer.is_available())
                tokenizer_name = self._tokenizer.name()
                if not tokenizer_available:
                    tokenizer_reason = self._tokenizer.unavailable_reason() or "分词器不可用"
            except Exception as exc:
                tokenizer_available = False
                tokenizer_reason = f"分词器检查失败: {exc}"

        strategy_requested = self._normalize_strategy(strategy)
        strategy_used = "rule"
        model_name = ""
        reranker_name = ""
        fallback_reason = ""
        if strategy_requested in {"auto", "model"}:
            self._emit_progress(
                progress,
                phase="model_loading",
                message="正在检查本地模型可用性...",
                indeterminate=True,
            )
            (
                strategy_used,
                model_name,
                reranker_name,
                fallback_reason,
            ) = self._resolve_strategy(
                strategy_requested,
                tokenizer_available=tokenizer_available,
                tokenizer_reason=tokenizer_reason,
            )
            if strategy_used == "model":
                self._logger.log_event(
                    "model_ready",
                    {
                        "strategy_requested": strategy_requested,
                        "model_name": model_name,
                        "reranker_name": reranker_name,
                    },
                )
                self._emit_progress(
                    progress,
                    phase="model_ready",
                    message=f"模型已就绪: embedding={model_name}, reranker={reranker_name}",
                    current=0,
                    total=1,
                )
            elif fallback_reason:
                self._logger.log_event(
                    "model_fallback_rule",
                    {
                        "strategy_requested": strategy_requested,
                        "fallback_reason": fallback_reason,
                    },
                )
                self._emit_progress(
                    progress,
                    phase="model_fallback_rule",
                    message=f"回退到规则模式: {fallback_reason}",
                    current=0,
                    total=1,
                )
        else:
            strategy_used = "rule"

        videos = self._collect_videos(scope_normalized)
        total = len(videos)
        cleared_pending_candidates = self._repo.clear_pending_tag_candidates()
        blacklist_keys = self._prepare_blacklist_keys(self._repo.list_blacklist_terms())
        config = {
            "min_df": min_df,
            "max_tags_per_video": max_tags_per_video,
            "max_terms": max_terms,
            "source": "ai_title",
            "scope": scope_normalized,
            "strategy_requested": strategy_requested,
            "strategy_used": strategy_used,
            "model_name": model_name,
            "reranker_name": reranker_name,
            "fallback_reason": fallback_reason,
            "tokenizer_name": tokenizer_name,
            "tokenizer_available": tokenizer_available,
            "tokenizer_reason": tokenizer_reason,
            "mapping_mode": "existing_tags_only",
            "unmatched_sink": "tag_candidates",
            "blacklist_match_mode": "contains",
            "blacklist_terms": len(blacklist_keys),
            "pending_candidates_cleared_on_start": cleared_pending_candidates,
            "thresholds": threshold_config.to_payload(),
        }

        self._logger.set_library_root(root)
        self._logger.begin_run(total_videos=total, config=config)
        self._logger.log_event(
            "candidate_pool_reset",
            {
                "cleared_pending_candidates": cleared_pending_candidates,
            },
        )
        self._logger.log_event(
            "blacklist_loaded",
            {
                "match_mode": "contains",
                "term_count": len(blacklist_keys),
            },
        )
        self._logger.log_event(
            "tokenizer_status",
            {
                "tokenizer_name": tokenizer_name,
                "tokenizer_available": tokenizer_available,
                "tokenizer_reason": tokenizer_reason,
            },
        )
        if threshold_config.warning:
            self._logger.log_event(
                "thresholds_warning",
                {
                    "source_path": threshold_config.source_path,
                    "warning": threshold_config.warning,
                },
            )
        else:
            self._logger.log_event(
                "thresholds_loaded",
                {
                    "source_path": threshold_config.source_path,
                    "thresholds": threshold_config.to_payload(),
                },
            )
        rule_matched_videos = 0
        rule_matched_relations = 0
        semantic_auto_hits = 0
        semantic_pending_hits = 0
        semantic_rejected_hits = 0
        blacklist_blocked_hits = 0
        self._emit_progress(
            progress,
            phase="tag_prepare",
            message="准备进行标题标签提取",
            current=0,
            total=max(1, total),
            indeterminate=(total == 0),
        )

        if total == 0:
            result = TagMiningResult(
                processed_videos=0,
                selected_terms=0,
                tagged_videos=0,
                created_relations=0,
                elapsed_ms=int((time.time() - started) * 1000),
                status="completed",
                strategy_requested=strategy_requested,
                strategy_used=strategy_used,
                model_name=model_name,
                reranker_name=reranker_name,
                fallback_reason=fallback_reason,
                scope=scope_normalized,
                threshold_config_path=threshold_config.source_path,
                pending_candidate_terms=0,
                pending_candidate_hits=0,
                semantic_auto_hits=0,
                semantic_pending_hits=0,
                semantic_rejected_hits=0,
                top_terms=[],
            )
            self._logger.log_summary(
                {
                    "processed_videos": result.processed_videos,
                    "selected_terms": result.selected_terms,
                    "tagged_videos": result.tagged_videos,
                    "created_relations": result.created_relations,
                    "elapsed_ms": result.elapsed_ms,
                    "status": result.status,
                    "strategy_requested": result.strategy_requested,
                    "strategy_used": result.strategy_used,
                    "model_name": result.model_name,
                    "reranker_name": result.reranker_name,
                    "fallback_reason": result.fallback_reason,
                    "scope": result.scope,
                    "threshold_config_path": result.threshold_config_path,
                    "rule_matched_videos": rule_matched_videos,
                    "rule_matched_relations": rule_matched_relations,
                    "pending_candidate_terms": result.pending_candidate_terms,
                    "pending_candidate_hits": result.pending_candidate_hits,
                    "semantic_auto_hits": result.semantic_auto_hits,
                    "semantic_pending_hits": result.semantic_pending_hits,
                    "semantic_rejected_hits": result.semantic_rejected_hits,
                    "top_terms": result.top_terms,
                }
            )
            self._emit_progress(
                progress,
                phase="tag_done",
                message="视频库中没有可处理的视频",
                current=1,
                total=1,
            )
            return result

        selected_terms: list[str] = []
        term_tf: Counter[str] = Counter()
        term_df: Counter[str] = Counter()
        terms_by_video_id: Dict[str, list[str]] = {}
        tagged_videos = 0
        processed_count = 0

        try:
            for idx, video in enumerate(videos, start=1):
                if self._is_stop_requested(should_stop):
                    raise _TagMiningCancelled(
                        phase="term_extract",
                        rel_path=video["rel_path"],
                        processed=processed_count,
                    )
                terms, blocked_hits = self._extract_terms(
                    video["effective_title"],
                    blacklist_keys=blacklist_keys,
                )
                unique_terms = self._dedupe_preserve(terms)
                terms_by_video_id[video["id"]] = unique_terms
                term_tf.update(terms)
                term_df.update(set(unique_terms))
                blacklist_blocked_hits += blocked_hits
                processed_count = idx
                self._emit_progress(
                    progress,
                    phase="term_extract",
                    message=f"提取词项: {video['rel_path']}",
                    current=idx,
                    total=total,
                    rel_path=video["rel_path"],
                )

            priority_terms = [
                t
                for t in term_df.keys()
                if self._is_semantic_priority_term(t) and self._is_valid_term(t)
            ]
            priority_set = set(priority_terms)
            non_priority_terms = [
                t
                for t, df in term_df.items()
                if df >= min_df and t not in priority_set and self._is_valid_term(t)
            ]
            priority_terms.sort(
                key=lambda t: (
                    term_df[t],
                    term_tf[t],
                    len(t),
                    t,
                ),
                reverse=True,
            )
            non_priority_terms.sort(
                key=lambda t: (
                    term_df[t],
                    term_tf[t],
                    len(t),
                    t,
                ),
                reverse=True,
            )
            selected_terms = self._dedupe_preserve(
                priority_terms + non_priority_terms[:max_terms]
            )
            selected_set = set(selected_terms)
            self._logger.log_event(
                "term_selection_summary",
                {
                    "priority_terms": len(priority_terms),
                    "non_priority_terms": len(non_priority_terms),
                    "selected_terms": len(selected_terms),
                    "max_terms": max_terms,
                },
            )

            known_tags = self._repo.list_tags()
            whitelist_tags = [
                str(item.get("name") or "").strip()
                for item in known_tags
                if str(item.get("name") or "").strip()
            ]
            whitelist_by_key = {tag_name.lower(): tag_name for tag_name in whitelist_tags}
            alias_memory_rows = self._repo.list_tag_alias_memory()
            alias_memory_by_key: Dict[str, str] = {}
            for row in alias_memory_rows:
                status = str(row.get("status") or "").strip().lower()
                if status != "verified":
                    continue
                alias_name = str(row.get("alias") or "").strip()
                mapped_tag = str(row.get("tag_name") or "").strip()
                mapped_tag_key = mapped_tag.lower()
                if not alias_name or mapped_tag_key not in whitelist_by_key:
                    continue
                mapped_tag = whitelist_by_key[mapped_tag_key]
                alias_key = self._normalize_lookup_key(alias_name)
                if not alias_key:
                    continue
                alias_memory_by_key[alias_key] = mapped_tag
            rule_matched_by_video_id, rule_matched_relations = self._rule_match_tags(
                videos=videos,
                whitelist_tags=whitelist_tags,
            )
            rule_matched_videos = sum(
                1 for terms in rule_matched_by_video_id.values() if terms
            )
            self._logger.log_event(
                "rule_match_summary",
                {
                    "rule_matched_videos": rule_matched_videos,
                    "rule_matched_relations": rule_matched_relations,
                    "alias_memory_size": len(alias_memory_by_key),
                },
            )
            semantic_decision_by_term: Dict[str, Dict[str, Any]] = {}
            if strategy_used == "model" and selected_terms and whitelist_tags:
                if self._is_stop_requested(should_stop):
                    raise _TagMiningCancelled(
                        phase="semantic_prepare",
                        rel_path="",
                        processed=processed_count,
                    )
                self._emit_progress(
                    progress,
                    phase="semantic_prepare",
                    message=f"正在向量化 {len(selected_terms)} 个候选词...",
                    current=0,
                    total=1,
                    indeterminate=True,
                )
                try:
                    semantic_decision_by_term = self._build_semantic_term_tag_decisions(
                        terms=selected_terms,
                        whitelist_tags=whitelist_tags,
                        threshold_config=threshold_config,
                    )
                except Exception as exc:
                    if strategy_requested == "model":
                        raise
                    strategy_used = "rule"
                    fallback_reason = f"语义判定失败: {exc}"
                    self._logger.log_event(
                        "model_fallback_rule",
                        {
                            "strategy_requested": strategy_requested,
                            "fallback_reason": fallback_reason,
                        },
                    )
                    self._emit_progress(
                        progress,
                        phase="model_fallback_rule",
                        message=f"回退到规则模式: {fallback_reason}",
                        current=0,
                        total=1,
                    )
                else:
                    semantic_auto_terms = sum(
                        1
                        for item in semantic_decision_by_term.values()
                        if str(item.get("decision") or "") == "auto"
                    )
                    semantic_pending_terms = sum(
                        1
                        for item in semantic_decision_by_term.values()
                        if str(item.get("decision") or "") == "pending"
                    )
                    semantic_reject_terms = sum(
                        1
                        for item in semantic_decision_by_term.values()
                        if str(item.get("decision") or "") == "reject"
                    )
                    self._logger.log_event(
                        "semantic_ready",
                        {
                            "embedded_terms": len(selected_terms),
                            "semantic_scored_terms": len(semantic_decision_by_term),
                            "semantic_auto_terms": semantic_auto_terms,
                            "semantic_pending_terms": semantic_pending_terms,
                            "semantic_reject_terms": semantic_reject_terms,
                            "thresholds": threshold_config.to_payload(),
                        },
                    )
                    self._emit_progress(
                        progress,
                        phase="semantic_ready",
                        message=(
                            "语义判定完成："
                            f"自动={semantic_auto_terms}，待审核={semantic_pending_terms}，"
                            f"拒绝={semantic_reject_terms}"
                        ),
                        current=1,
                        total=1,
                    )

            tags_by_video_id: Dict[str, list[str]] = {}
            candidate_hits_by_term: Dict[str, list[str]] = {}
            pending_hit_count = 0
            semantic_auto_hits = 0
            semantic_pending_hits = 0
            semantic_rejected_hits = 0
            tagged_videos = 0
            processed_count = 0
            for idx, video in enumerate(videos, start=1):
                if self._is_stop_requested(should_stop):
                    raise _TagMiningCancelled(
                        phase="tag_assign",
                        rel_path=video["rel_path"],
                        processed=processed_count,
                    )
                current_terms = terms_by_video_id.get(video["id"], [])
                candidate = [t for t in current_terms if t in selected_set]
                candidate = self._dedupe_preserve(candidate)
                candidate.sort(
                    key=lambda t: (
                        term_df[t],
                        term_tf[t],
                        len(t),
                        t,
                    ),
                    reverse=True,
                )
                selected = candidate

                approved_terms: list[str] = list(
                    rule_matched_by_video_id.get(video["id"], [])
                )
                pending_terms: list[str] = []
                semantic_logs: list[Dict[str, str | float]] = []
                for term in selected:
                    mapped = whitelist_by_key.get(term.lower())
                    if mapped:
                        approved_terms.append(mapped)
                        continue
                    alias_mapped = alias_memory_by_key.get(
                        self._normalize_lookup_key(term)
                    )
                    if alias_mapped:
                        approved_terms.append(alias_mapped)
                        semantic_auto_hits += 1
                        semantic_logs.append(
                            {
                                "term": term,
                                "best_concept": "",
                                "best_alias": term,
                                "best_tag": alias_mapped,
                                "decision": "alias_memory",
                                "auto_tags": alias_mapped,
                                "pending_tags": "",
                                "score": 1.0,
                                "recall_score": 1.0,
                                "auto_threshold": 1.0,
                                "pending_threshold": 1.0,
                            }
                        )
                        continue
                    semantic_decision = semantic_decision_by_term.get(term)
                    if semantic_decision is None:
                        pending_terms.append(term)
                        candidate_hits_by_term.setdefault(term, [])
                        candidate_hits_by_term[term].append(video["id"])
                        pending_hit_count += 1
                        continue

                    semantic_mode = str(semantic_decision.get("decision") or "")
                    auto_tags = self._filter_existing_tags(
                        self._to_str_list(semantic_decision.get("auto_tags")),
                        whitelist_by_key,
                    )
                    pending_tags = self._filter_existing_tags(
                        self._to_str_list(semantic_decision.get("pending_tags")),
                        whitelist_by_key,
                    )
                    best_tag = str(semantic_decision.get("best_tag") or "").strip()
                    best_concept = str(semantic_decision.get("best_concept") or "").strip()
                    best_alias = str(semantic_decision.get("best_alias") or "").strip()
                    semantic_score = float(
                        semantic_decision.get("rerank_score") or 0.0
                    )
                    semantic_logs.append(
                        {
                            "term": term,
                            "best_concept": best_concept,
                            "best_alias": best_alias,
                            "best_tag": best_tag,
                            "decision": semantic_mode,
                            "auto_tags": ",".join(auto_tags[:3]),
                            "pending_tags": ",".join(pending_tags[:3]),
                            "score": round(semantic_score, 4),
                            "recall_score": round(
                                float(semantic_decision.get("recall_score") or 0.0), 4
                            ),
                            "auto_threshold": round(
                                float(semantic_decision.get("auto_threshold") or 0.0), 4
                            ),
                            "pending_threshold": round(
                                float(semantic_decision.get("pending_threshold") or 0.0), 4
                            ),
                        }
                    )
                    if auto_tags:
                        approved_terms.extend(auto_tags)
                        semantic_auto_hits += len(auto_tags)
                        continue
                    if semantic_mode == "pending" or pending_tags:
                        pending_terms.append(term)
                        candidate_hits_by_term.setdefault(term, [])
                        candidate_hits_by_term[term].append(video["id"])
                        pending_hit_count += 1
                        semantic_pending_hits += 1
                        continue
                    pending_terms.append(term)
                    candidate_hits_by_term.setdefault(term, [])
                    candidate_hits_by_term[term].append(video["id"])
                    pending_hit_count += 1
                    semantic_rejected_hits += 1
                    continue
                pending_terms = self._dedupe_preserve(pending_terms)

                approved_terms = self._filter_existing_tags(
                    self._dedupe_preserve(approved_terms),
                    whitelist_by_key,
                )
                if len(approved_terms) > max_tags_per_video:
                    approved_terms = approved_terms[:max_tags_per_video]
                if approved_terms:
                    tagged_videos += 1
                tags_by_video_id[video["id"]] = approved_terms
                processed_count = idx

                self._logger.log_video_processed(
                    video_id=video["id"],
                    rel_path=video["rel_path"],
                    terms=current_terms,
                    selected_terms=approved_terms,
                )
                if pending_terms:
                    self._logger.log_event(
                        "candidate_terms_detected",
                        {
                            "video_id": video["id"],
                            "rel_path": video["rel_path"],
                            "pending_terms": pending_terms,
                        },
                    )
                if semantic_logs:
                    self._logger.log_event(
                        "semantic_terms_scored",
                        {
                            "video_id": video["id"],
                            "rel_path": video["rel_path"],
                            "semantic_terms": semantic_logs,
                        },
                    )
                self._emit_progress(
                    progress,
                    phase="tag_assign",
                    message=f"分配标签: {video['rel_path']}",
                    current=idx,
                    total=total,
                    rel_path=video["rel_path"],
                )

            if self._is_stop_requested(should_stop):
                raise _TagMiningCancelled(
                    phase="before_write",
                    rel_path="",
                    processed=processed_count,
                )

            processed_video_ids = [video["id"] for video in videos]
            created_relations = self._repo.apply_ai_title_tags(
                tags_by_video_id,
                target_video_ids=processed_video_ids,
            )
            pending_candidates = self._repo.upsert_tag_candidates(candidate_hits_by_term)
            self._repo.mark_title_tag_mined(processed_video_ids, _now_epoch())
            self._logger.log_event(
                "candidate_summary",
                {
                    "rule_matched_videos": rule_matched_videos,
                    "rule_matched_relations": rule_matched_relations,
                    "semantic_auto_hits": semantic_auto_hits,
                    "semantic_pending_hits": semantic_pending_hits,
                    "semantic_rejected_hits": semantic_rejected_hits,
                    "blacklist_blocked_hits": blacklist_blocked_hits,
                    "blacklist_term_count": len(blacklist_keys),
                    "pending_candidate_terms": pending_candidates,
                    "pending_candidate_hits": pending_hit_count,
                },
            )

            top_terms = [
                f"{term} ({term_df[term]}/{term_tf[term]})"
                for term in selected_terms[:20]
            ]
            elapsed_ms = int((time.time() - started) * 1000)
            result = TagMiningResult(
                processed_videos=total,
                selected_terms=len(selected_terms),
                tagged_videos=tagged_videos,
                created_relations=created_relations,
                elapsed_ms=elapsed_ms,
                status="completed",
                strategy_requested=strategy_requested,
                strategy_used=strategy_used,
                model_name=model_name,
                reranker_name=reranker_name,
                fallback_reason=fallback_reason,
                scope=scope_normalized,
                threshold_config_path=threshold_config.source_path,
                pending_candidate_terms=pending_candidates,
                pending_candidate_hits=pending_hit_count,
                semantic_auto_hits=semantic_auto_hits,
                semantic_pending_hits=semantic_pending_hits,
                semantic_rejected_hits=semantic_rejected_hits,
                top_terms=top_terms,
            )
            self._logger.log_summary(
                {
                    "processed_videos": result.processed_videos,
                    "selected_terms": result.selected_terms,
                    "tagged_videos": result.tagged_videos,
                    "created_relations": result.created_relations,
                    "elapsed_ms": result.elapsed_ms,
                    "status": result.status,
                    "strategy_requested": result.strategy_requested,
                    "strategy_used": result.strategy_used,
                    "model_name": result.model_name,
                    "reranker_name": result.reranker_name,
                    "fallback_reason": result.fallback_reason,
                    "scope": result.scope,
                    "threshold_config_path": result.threshold_config_path,
                    "pending_candidate_terms": result.pending_candidate_terms,
                    "pending_candidate_hits": result.pending_candidate_hits,
                    "semantic_auto_hits": result.semantic_auto_hits,
                    "semantic_pending_hits": result.semantic_pending_hits,
                    "semantic_rejected_hits": result.semantic_rejected_hits,
                    "blacklist_blocked_hits": blacklist_blocked_hits,
                    "blacklist_term_count": len(blacklist_keys),
                    "cleared_pending_candidates": cleared_pending_candidates,
                    "top_terms": result.top_terms,
                }
            )
            self._emit_progress(
                progress,
                phase="tag_done",
                message=(
                    f"标签提取完成: 规则命中={rule_matched_relations}, 已打标={result.tagged_videos}, "
                    f"新增关联={result.created_relations}, "
                    f"语义自动映射={result.semantic_auto_hits}, "
                    f"语义待审词项={result.semantic_pending_hits}, "
                    f"语义未命中={result.semantic_rejected_hits}, "
                    f"待审核标签={result.pending_candidate_terms}"
                ),
                current=1,
                total=1,
            )
            return result
        except _TagMiningCancelled as cancelled:
            elapsed_ms = int((time.time() - started) * 1000)
            result = TagMiningResult(
                processed_videos=max(0, cancelled.processed),
                selected_terms=len(selected_terms),
                tagged_videos=tagged_videos,
                created_relations=0,
                elapsed_ms=elapsed_ms,
                status="cancelled",
                strategy_requested=strategy_requested,
                strategy_used=strategy_used,
                model_name=model_name,
                reranker_name=reranker_name,
                fallback_reason=fallback_reason,
                scope=scope_normalized,
                threshold_config_path=threshold_config.source_path,
                pending_candidate_terms=0,
                pending_candidate_hits=0,
                semantic_auto_hits=semantic_auto_hits,
                semantic_pending_hits=semantic_pending_hits,
                semantic_rejected_hits=semantic_rejected_hits,
                top_terms=[],
            )
            self._logger.log_summary(
                {
                    "processed_videos": result.processed_videos,
                    "selected_terms": result.selected_terms,
                    "tagged_videos": result.tagged_videos,
                    "created_relations": result.created_relations,
                    "elapsed_ms": result.elapsed_ms,
                    "status": result.status,
                    "strategy_requested": result.strategy_requested,
                    "strategy_used": result.strategy_used,
                    "model_name": result.model_name,
                    "reranker_name": result.reranker_name,
                    "fallback_reason": result.fallback_reason,
                    "scope": result.scope,
                    "threshold_config_path": result.threshold_config_path,
                    "pending_candidate_terms": result.pending_candidate_terms,
                    "pending_candidate_hits": result.pending_candidate_hits,
                    "semantic_auto_hits": result.semantic_auto_hits,
                    "semantic_pending_hits": result.semantic_pending_hits,
                    "semantic_rejected_hits": result.semantic_rejected_hits,
                    "cancelled_phase": cancelled.phase,
                    "rel_path": cancelled.rel_path,
                    "top_terms": result.top_terms,
                }
            )
            self._emit_progress(
                progress,
                phase="tag_cancelled",
                message=(
                    "标签提取已取消"
                    if not cancelled.rel_path
                    else f"标签提取已取消: {cancelled.rel_path}"
                ),
                current=cancelled.processed,
                total=total,
                rel_path=cancelled.rel_path,
                indeterminate=False,
            )
            return result
        except Exception as exc:
            self._logger.log_error(stage="tag_mining", message=str(exc))
            self._emit_progress(
                progress,
                phase="tag_error",
                message=f"标签提取失败: {exc}",
                current=0,
                total=1,
            )
            raise

    def _collect_videos(self, scope: str) -> list[Dict[str, str]]:
        rows: list[Dict[str, str]] = []
        for video_id, info in self._repo.videos().items():
            if bool(info.get("missing")):
                continue

            rel_path = str(info.get("rel_path") or "")
            if not rel_path:
                continue
            if scope == "new_only" and int(info.get("title_tag_mined_epoch") or 0) > 0:
                continue

            filename = str(info.get("filename") or Path(rel_path).name)
            stem = Path(filename).stem
            title_guess = str(info.get("title_guess") or "").strip()
            effective_title = stem
            if title_guess and title_guess.lower() != stem.lower():
                effective_title = f"{title_guess} {stem}"

            rows.append(
                {
                    "id": str(video_id),
                    "rel_path": rel_path,
                    "effective_title": effective_title,
                }
            )

        rows.sort(key=lambda item: item["rel_path"].lower())
        return rows

    def _rule_match_tags(
        self, videos: list[Dict[str, str]], whitelist_tags: list[str]
    ) -> tuple[Dict[str, list[str]], int]:
        normalized_pairs: list[tuple[str, str]] = []
        seen = set()
        for tag_name in whitelist_tags:
            normalized = self._normalize_text(tag_name)
            if not normalized or len(normalized) < 2:
                continue
            key = (normalized, tag_name.lower())
            if key in seen:
                continue
            seen.add(key)
            normalized_pairs.append((normalized, tag_name))

        # 优先匹配更长标签，减少短词误命中。
        normalized_pairs.sort(key=lambda item: len(item[0]), reverse=True)

        matched_by_video: Dict[str, list[str]] = {}
        relation_count = 0
        for video in videos:
            normalized_title = self._normalize_text(video.get("effective_title", ""))
            if not normalized_title:
                continue
            compact_title = normalized_title.replace(" ", "")
            hits: list[str] = []
            for normalized_tag, tag_name in normalized_pairs:
                compact_tag = normalized_tag.replace(" ", "")
                if normalized_tag in normalized_title:
                    hits.append(tag_name)
                    continue
                if len(compact_tag) >= 2 and compact_tag in compact_title:
                    hits.append(tag_name)
            hits = self._dedupe_preserve(hits)
            if hits:
                matched_by_video[str(video["id"])] = hits
                relation_count += len(hits)
        return matched_by_video, relation_count

    def _extract_terms(
        self,
        text: str,
        blacklist_keys: Optional[list[str]] = None,
    ) -> tuple[list[str], int]:
        normalized = self._normalize_text(text)
        if not normalized:
            return ([], 0)

        terms: list[str] = []
        terms.extend(self._alnum_terms(normalized))
        terms.extend(self._age_terms(normalized))
        terms.extend(self._grade_terms(normalized))
        tokenizer_terms = self._tokenizer_terms(normalized)
        if tokenizer_terms:
            terms.extend(tokenizer_terms)
        else:
            terms.extend(self._chinese_terms(normalized))
        cleaned_terms = [t for t in terms if self._is_valid_term(t)]
        blocked_hits = 0
        filtered_terms: list[str] = []
        active_blacklist = list(blacklist_keys or [])
        for term in cleaned_terms:
            if self._matches_blacklist_term(term, active_blacklist):
                blocked_hits += 1
                continue
            filtered_terms.append(term)
        return (self._dedupe_preserve(filtered_terms), blocked_hits)

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text or "")
        normalized = normalized.replace("_", " ").replace("-", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip().lower()

    def _normalize_lookup_key(self, text: str) -> str:
        return self._normalize_text(text).replace(" ", "")

    def _alnum_terms(self, normalized: str) -> list[str]:
        terms: list[str] = []
        for token in _ALNUM_RE.findall(normalized):
            token = token.strip().lower()
            if len(token) < 2:
                continue
            terms.append(token)
        return terms

    def _age_terms(self, normalized: str) -> list[str]:
        terms: list[str] = []
        for match in _AGE_TERM_RE.finditer(normalized):
            try:
                age = int(match.group(1))
            except Exception:
                continue
            if age <= 0:
                continue
            terms.append(f"{age}岁")
        return terms

    def _grade_terms(self, normalized: str) -> list[str]:
        terms: list[str] = []
        for match in _GRADE_TERM_RE.finditer(normalized):
            token = str(match.group(0) or "").strip().replace(" ", "")
            if len(token) >= 2:
                terms.append(token)
        return terms

    def _tokenizer_terms(self, normalized: str) -> list[str]:
        if self._tokenizer is None:
            return []
        try:
            raw_tokens = self._tokenizer.tokenize(normalized)
        except Exception:
            return []
        terms: list[str] = []
        for raw_token in raw_tokens:
            token = self._normalize_text(str(raw_token))
            if not token:
                continue

            for chunk in _CHINESE_RE.findall(token):
                if 2 <= len(chunk) <= 12:
                    terms.append(chunk)
            for chunk in _ALNUM_RE.findall(token):
                if len(chunk) >= 2:
                    terms.append(chunk.lower())

        return terms

    def _chinese_terms(self, normalized: str) -> list[str]:
        terms: list[str] = []
        for chunk in _CHINESE_RE.findall(normalized):
            if len(chunk) < 2:
                continue
            if 2 <= len(chunk) <= 8:
                terms.append(chunk)
            max_n = min(4, len(chunk))
            for n in range(2, max_n + 1):
                for i in range(0, len(chunk) - n + 1):
                    gram = chunk[i : i + n]
                    terms.append(gram)
        return terms

    def _is_valid_term(self, term: str) -> bool:
        t = term.strip().lower()
        if len(t) < 2:
            return False
        if self._is_noise_term(t):
            return False
        if t.isdigit():
            return False
        return True

    def _is_noise_term(self, term: str) -> bool:
        t = str(term or "").strip().lower()
        if not t:
            return True
        if _HEX_ID_RE.fullmatch(t):
            return True
        if _MIXED_ID_RE.fullmatch(t):
            return True
        # Likely UUID chunks or machine-generated identifiers.
        if len(t) >= 16 and any(c.isdigit() for c in t) and any("a" <= c <= "z" for c in t):
            return True
        return False

    def _dedupe_preserve(self, values: Iterable[str]) -> list[str]:
        out: list[str] = []
        seen = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
        return out

    def _prepare_blacklist_keys(self, terms: list[str]) -> list[str]:
        keys = sorted(
            {
                self._normalize_lookup_key(term)
                for term in terms
                if len(self._normalize_lookup_key(term)) >= 2
            },
            key=len,
            reverse=True,
        )
        return keys

    def _matches_blacklist_term(self, term: str, blacklist_keys: list[str]) -> bool:
        lookup = self._normalize_lookup_key(term)
        if len(lookup) < 2:
            return False
        for blocked in blacklist_keys:
            if blocked and blocked in lookup:
                return True
        return False

    def _to_str_list(self, value: Any) -> list[str]:
        if isinstance(value, (list, tuple, set)):
            items = [str(item).strip() for item in value if str(item).strip()]
            return self._dedupe_preserve(items)
        return []

    def _filter_existing_tags(
        self,
        tags: Iterable[str],
        whitelist_by_key: Dict[str, str],
    ) -> list[str]:
        normalized: list[str] = []
        for raw_tag in tags:
            tag_name = str(raw_tag or "").strip()
            if not tag_name:
                continue
            mapped = whitelist_by_key.get(tag_name.lower())
            if mapped:
                normalized.append(mapped)
        return self._dedupe_preserve(normalized)

    def _normalize_strategy(self, strategy: str) -> str:
        value = (strategy or "auto").strip().lower()
        if value not in {"auto", "rule", "model"}:
            raise ValueError("strategy 参数必须是: auto / rule / model")
        return value

    def _normalize_scope(self, scope: str) -> str:
        value = (scope or "all").strip().lower()
        if value not in {"all", "new_only"}:
            raise ValueError("scope 参数必须是: all / new_only")
        return value

    def _is_semantic_priority_term(self, term: str) -> bool:
        compact = self._normalize_text(term).replace(" ", "")
        if not compact:
            return False
        if _GRADE_TERM_RE.search(compact):
            return True
        if _AGE_TERM_RE.search(compact):
            return True
        return False

    def _resolve_strategy(
        self,
        requested: str,
        tokenizer_available: bool,
        tokenizer_reason: str,
    ) -> tuple[str, str, str, str]:
        if requested == "rule":
            return ("rule", "", "", "")

        if not tokenizer_available:
            reason = tokenizer_reason or "分词器不可用"
            if requested == "model":
                raise RuntimeError(f"请求模型策略，但分词器不可用: {reason}")
            return ("rule", "", "", f"分词器不可用: {reason}")

        if self._embedding_model is None:
            if requested == "model":
                raise RuntimeError("请求模型策略，但未配置模型提供器")
            return ("rule", "", "", "未配置 embedding 模型提供器")
        if self._reranker_model is None:
            if requested == "model":
                raise RuntimeError("请求模型策略，但未配置 reranker 模型提供器")
            return ("rule", "", "", "未配置 reranker 模型提供器")

        embedding_available = False
        try:
            embedding_available = self._embedding_model.is_available()
        except Exception as exc:
            if requested == "model":
                raise RuntimeError(f"请求模型策略，但 embedding 检查失败: {exc}")
            return ("rule", "", "", f"embedding 检查失败: {exc}")
        if not embedding_available:
            reason = self._embedding_model.unavailable_reason() or "embedding 模型不可用"
            if requested == "model":
                raise RuntimeError(f"请求模型策略，但 embedding 不可用: {reason}")
            return ("rule", "", "", f"embedding 不可用: {reason}")

        reranker_available = False
        try:
            reranker_available = self._reranker_model.is_available()
        except Exception as exc:
            if requested == "model":
                raise RuntimeError(f"请求模型策略，但 reranker 检查失败: {exc}")
            return ("rule", "", "", f"reranker 检查失败: {exc}")
        if not reranker_available:
            reason = self._reranker_model.unavailable_reason() or "reranker 模型不可用"
            if requested == "model":
                raise RuntimeError(f"请求模型策略，但 reranker 不可用: {reason}")
            return ("rule", "", "", f"reranker 不可用: {reason}")

        return (
            "model",
            self._embedding_model.name(),
            self._reranker_model.name(),
            "",
        )

    def _semantic_hint_tags(self, term: str, whitelist_tags: list[str]) -> list[str]:
        compact = self._normalize_text(term).replace(" ", "")
        if not compact:
            return []

        hints: list[str] = []
        if _GRADE_TERM_RE.search(compact):
            for tag in whitelist_tags:
                if "高中" in tag or "中学生" in tag:
                    hints.append(tag)

        age_match = _AGE_TERM_RE.search(compact)
        if age_match:
            try:
                age = int(age_match.group(1))
            except Exception:
                age = 0
            if 0 < age <= 17:
                for tag in whitelist_tags:
                    if "稚嫩" in tag:
                        hints.append(tag)
                if not hints:
                    for tag in whitelist_tags:
                        if (
                            "中学生" in tag
                            or "高中" in tag
                            or "少女" in tag
                            or "未成年" in tag
                        ):
                            hints.append(tag)
        return self._dedupe_preserve(hints)[:2]

    def _build_semantic_term_tag_decisions(
        self,
        terms: list[str],
        whitelist_tags: list[str],
        threshold_config: TagMiningThresholdConfig,
    ) -> Dict[str, Dict[str, Any]]:
        if self._embedding_model is None or self._reranker_model is None:
            raise RuntimeError("embedding/reranker 模型未配置")

        clean_terms = self._dedupe_preserve(
            [t for t in terms if self._is_valid_term(t) and len(t.strip()) >= 2]
        )
        clean_tags = self._dedupe_preserve(
            [str(t).strip() for t in whitelist_tags if len(str(t).strip()) >= 2]
        )
        if not clean_terms or not clean_tags:
            return {}

        term_vectors = self._embedding_model.embed(clean_terms)
        tag_vectors = self._embedding_model.embed(clean_tags)
        if len(term_vectors) != len(clean_terms):
            raise RuntimeError("embedding 词向量数量异常")
        if len(tag_vectors) != len(clean_tags):
            raise RuntimeError("embedding 标签向量数量异常")

        decisions: Dict[str, Dict[str, Any]] = {}
        recall_top_k = max(1, int(threshold_config.recall_top_k))
        recall_min_score = float(threshold_config.recall_min_score)

        for term, term_vec in zip(clean_terms, term_vectors):
            hint_tags = self._semantic_hint_tags(term, clean_tags)

            recall_score_by_tag: Dict[str, float] = {}
            for idx, tag_vec in enumerate(tag_vectors):
                score = self._cosine_similarity(term_vec, tag_vec)
                recall_score_by_tag[clean_tags[idx]] = float(score)

            hint_candidates: list[tuple[str, float]] = []
            seen_hints = set()
            for hint_tag in hint_tags:
                if hint_tag in seen_hints:
                    continue
                seen_hints.add(hint_tag)
                base_score = float(recall_score_by_tag.get(hint_tag, 0.0))
                boosted_score = max(base_score, recall_min_score)
                recall_score_by_tag[hint_tag] = boosted_score
                hint_candidates.append((hint_tag, boosted_score))

            recall_scored = sorted(
                [
                    (tag_name, float(score))
                    for tag_name, score in recall_score_by_tag.items()
                    if float(score) >= recall_min_score and tag_name not in seen_hints
                ],
                key=lambda item: item[1],
                reverse=True,
            )
            recall_candidates = (hint_candidates + recall_scored)[:recall_top_k]
            if not recall_candidates:
                fallback_threshold = threshold_config.defaults
                decisions[term] = {
                    "decision": "reject",
                    "best_tag": "",
                    "best_concept": "",
                    "best_alias": "",
                    "auto_tags": [],
                    "pending_tags": [],
                    "rerank_score": 0.0,
                    "recall_score": 0.0,
                    "auto_threshold": float(fallback_threshold.auto_apply),
                    "pending_threshold": float(fallback_threshold.pending_review),
                }
                continue

            candidate_tags = [tag for tag, _ in recall_candidates]
            raw_scores = self._reranker_model.rerank(term, candidate_tags)
            if len(raw_scores) != len(candidate_tags):
                raise RuntimeError("reranker 输出数量异常")

            reranked: list[tuple[str, float, float, float, float]] = []
            for idx, raw_score in enumerate(raw_scores):
                rerank_score = self._sigmoid(float(raw_score))
                recall_score = float(recall_candidates[idx][1])
                tag_name = candidate_tags[idx]
                tag_threshold = threshold_config.threshold_for(tag_name)
                reranked.append(
                    (
                        tag_name,
                        rerank_score,
                        recall_score,
                        float(tag_threshold.auto_apply),
                        float(tag_threshold.pending_review),
                    )
                )
            reranked.sort(key=lambda item: (item[1], item[2], len(item[0])), reverse=True)
            if not reranked:
                continue

            best_tag, best_rerank_score, best_recall_score, _, _ = reranked[0]
            keep_margin = 0.06
            auto_tags: list[str] = []
            pending_tags: list[str] = []
            for tag_name, rerank_score, _recall_score, auto_threshold, pending_threshold in reranked:
                if rerank_score < (best_rerank_score - keep_margin):
                    continue
                if rerank_score >= auto_threshold:
                    auto_tags.append(tag_name)
                elif rerank_score >= pending_threshold:
                    pending_tags.append(tag_name)

            auto_tags = self._dedupe_preserve(auto_tags)[:2]
            pending_tags = [tag for tag in self._dedupe_preserve(pending_tags) if tag not in auto_tags][:2]
            decision = "reject"
            if auto_tags:
                decision = "auto"
            elif pending_tags:
                decision = "pending"

            primary_threshold = threshold_config.threshold_for(best_tag)
            decisions[term] = {
                "decision": decision,
                "best_tag": best_tag,
                "best_concept": "",
                "best_alias": "",
                "auto_tags": auto_tags,
                "pending_tags": pending_tags,
                "rerank_score": float(best_rerank_score),
                "recall_score": float(best_recall_score),
                "auto_threshold": float(primary_threshold.auto_apply),
                "pending_threshold": float(primary_threshold.pending_review),
                "reason": "model_hint" if (hint_tags and best_tag in set(hint_tags)) else "model",
            }
        return decisions

    def _sigmoid(self, value: float) -> float:
        if value >= 0:
            z = math.exp(-float(value))
            return float(1.0 / (1.0 + z))
        z = math.exp(float(value))
        return float(z / (1.0 + z))

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        size = min(len(left), len(right))
        if size <= 0:
            return 0.0
        return float(sum(float(left[i]) * float(right[i]) for i in range(size)))

    def _is_stop_requested(
        self, should_stop: Optional[Callable[[], bool]]
    ) -> bool:
        if should_stop is None:
            return False
        try:
            return bool(should_stop())
        except Exception:
            return False

    def _emit_progress(
        self,
        callback: Optional[TagMiningProgressCallback],
        phase: str,
        message: str,
        current: int = 0,
        total: int = 0,
        indeterminate: bool = False,
        rel_path: str = "",
    ) -> None:
        if callback is None:
            return
        try:
            callback(
                TagMiningProgress(
                    phase=phase,
                    message=message,
                    current=current,
                    total=total,
                    indeterminate=indeterminate,
                    rel_path=rel_path,
                )
            )
        except Exception:
            pass
