from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional


_MODEL_MARKERS = (
    "config.json",
    "tokenizer_config.json",
)

_WEIGHT_MARKERS = (
    "pytorch_model.bin",
    "model.safetensors",
)

_MODEL_SPECS: dict[str, dict[str, Any]] = {
    "bge-reranker-base": {
        "repo_id": "BAAI/bge-reranker-base",
        "aliases": {
            "base",
            "reranker-base",
            "bge-reranker-base",
            "baai/bge-reranker-base",
        },
    },
    "bge-reranker-large": {
        "repo_id": "BAAI/bge-reranker-large",
        "aliases": {
            "large",
            "reranker-large",
            "bge-reranker-large",
            "baai/bge-reranker-large",
        },
    },
}

_ALIAS_TO_KEY: dict[str, str] = {}
for _key, _spec in _MODEL_SPECS.items():
    _aliases = {str(a).strip().lower() for a in _spec.get("aliases", set())}
    _aliases.add(_key.lower())
    _aliases.add(str(_spec.get("repo_id") or "").strip().lower())
    for _alias in _aliases:
        if _alias:
            _ALIAS_TO_KEY[_alias] = _key


class NoopRerankerModel:
    def __init__(self, reason: str = "reranker 模型已禁用") -> None:
        self._reason = reason

    def name(self) -> str:
        return "noop-reranker"

    def is_available(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return self._reason

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        raise RuntimeError(self._reason or "reranker 模型不可用")


class LocalBgeRerankerModel:
    """
    Local BGE reranker adapter.
    - 不在导入时强依赖 transformers / torch。
    - 支持 base / large 两个本地 reranker 目录。
    """

    def __init__(self, model_hint: str = "") -> None:
        self._model_hint = model_hint.strip()
        self._tokenizer = None
        self._backend = None
        self._torch = None
        self._device = "cpu"
        self._lock = threading.Lock()
        self._loaded = False
        self._name = ""
        self._reason = ""

    @classmethod
    def list_model_options(cls, project_root: Optional[Path] = None) -> list[dict[str, Any]]:
        root = cls._project_root(project_root)
        options: list[dict[str, Any]] = []
        for key, spec in _MODEL_SPECS.items():
            local_dir = cls._resolve_local_model_dir(root / "tools" / "models" / key, root)
            options.append(
                {
                    "key": key,
                    "repo_id": str(spec.get("repo_id") or ""),
                    "available": local_dir is not None,
                    "local_path": str(local_dir) if local_dir is not None else "",
                }
            )
        return options

    def name(self) -> str:
        self._ensure_loaded()
        return self._name or "transformers-reranker"

    def is_available(self) -> bool:
        self._ensure_loaded()
        return self._backend is not None and self._tokenizer is not None

    def unavailable_reason(self) -> str:
        self._ensure_loaded()
        return self._reason

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        self._ensure_loaded()
        if self._backend is None or self._tokenizer is None or self._torch is None:
            raise RuntimeError(self._reason or "reranker 模型不可用")
        if not candidates:
            return []

        pairs = [[query, candidate] for candidate in candidates]
        encoded = self._tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        if self._device != "cpu":
            encoded = {k: v.to(self._device) for k, v in encoded.items()}
        with self._torch.no_grad():
            outputs = self._backend(**encoded, return_dict=True)
            logits = outputs.logits
        if hasattr(logits, "detach"):
            logits = logits.detach()
        if hasattr(logits, "float"):
            logits = logits.float()
        if hasattr(logits, "cpu"):
            logits = logits.cpu()
        if hasattr(logits, "ndim"):
            if int(getattr(logits, "ndim")) == 2:
                width = int(getattr(logits, "shape")[1])
                logits = logits[:, 0] if width >= 1 else logits.reshape(-1)
        if hasattr(logits, "tolist"):
            values = logits.tolist()
        else:
            values = logits
        return [float(v) for v in values]

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._loaded = True

            model_ref = self._resolve_model_ref()
            if not model_ref:
                return

            try:
                import torch  # type: ignore
                from transformers import (  # type: ignore
                    AutoModelForSequenceClassification,
                    AutoTokenizer,
                    logging as transformers_logging,
                )
            except Exception as exc:
                self._reason = f"未安装 transformers/torch: {exc}"
                return

            try:
                transformers_logging.set_verbosity_error()
                tokenizer = AutoTokenizer.from_pretrained(model_ref, use_fast=False)
                backend = AutoModelForSequenceClassification.from_pretrained(model_ref)
                device = "cuda" if torch.cuda.is_available() else "cpu"
                backend.to(device)
                backend.eval()
                self._tokenizer = tokenizer
                self._backend = backend
                self._torch = torch
                self._device = device
                if not self._name:
                    self._name = f"reranker:{model_ref}"
            except Exception as exc:
                self._tokenizer = None
                self._backend = None
                self._torch = None
                self._reason = f"reranker 加载失败 '{model_ref}': {exc}"

    def _resolve_model_ref(self) -> Optional[str]:
        root = self._project_root()
        requested = self._model_hint or os.environ.get("MM_RERANKER_MODEL", "").strip()
        if not requested:
            requested = self._default_model_key(root)

        key = _ALIAS_TO_KEY.get(requested.strip().lower())
        if key:
            local_dir = self._resolve_local_model_dir(root / "tools" / "models" / key, root)
            if local_dir is None:
                self._reason = f"未找到本地 reranker：{key}。请放在 tools/models/{key} 目录下。"
                self._name = key
                return None
            self._name = key
            return str(local_dir)

        local_dir = self._resolve_local_model_dir(requested, root)
        if local_dir is not None:
            self._name = f"local:{local_dir.name}"
            return str(local_dir)

        if "/" in requested:
            self._name = requested
            return requested

        self._reason = f"未知 reranker 模型标识：{requested}"
        return None

    @classmethod
    def _default_model_key(cls, root: Path) -> str:
        for key in ("bge-reranker-large", "bge-reranker-base"):
            if cls._resolve_local_model_dir(root / "tools" / "models" / key, root) is not None:
                return key
        return "bge-reranker-large"

    @classmethod
    def _resolve_local_model_dir(cls, ref: str | Path, root: Path) -> Optional[Path]:
        ref_path = Path(ref)
        candidates = [ref_path]
        if not ref_path.is_absolute():
            candidates.append(root / ref_path)
        for candidate in candidates:
            resolved = cls._normalize_model_dir(candidate)
            if resolved is not None:
                return resolved
        return None

    @classmethod
    def _normalize_model_dir(cls, path: Path) -> Optional[Path]:
        if not path.exists() or not path.is_dir():
            return None
        if cls._looks_like_model_dir(path):
            return path
        child_dirs = [p for p in path.iterdir() if p.is_dir()]
        if len(child_dirs) == 1 and cls._looks_like_model_dir(child_dirs[0]):
            return child_dirs[0]
        return None

    @staticmethod
    def _looks_like_model_dir(path: Path) -> bool:
        for marker in _MODEL_MARKERS:
            if not (path / marker).exists():
                return False
        return any((path / marker).exists() for marker in _WEIGHT_MARKERS)

    @staticmethod
    def _project_root(explicit_root: Optional[Path] = None) -> Path:
        if explicit_root is not None:
            return explicit_root
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]
