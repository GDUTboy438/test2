from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional


_MODEL_MARKERS = (
    "config.json",
    "modules.json",
    "tokenizer_config.json",
)

_MODEL_SPECS: dict[str, dict[str, Any]] = {
    "bge-small-zh-v1.5": {
        "repo_id": "BAAI/bge-small-zh-v1.5",
        "aliases": {
            "small",
            "bge-small",
            "bge-small-zh-v1.5",
            "baai/bge-small-zh-v1.5",
        },
    },
    "bge-base-zh-v1.5": {
        "repo_id": "BAAI/bge-base-zh-v1.5",
        "aliases": {
            "base",
            "bge-base",
            "bge-base-zh-v1.5",
            "baai/bge-base-zh-v1.5",
        },
    },
    "bge-large-zh-v1.5": {
        "repo_id": "BAAI/bge-large-zh-v1.5",
        "aliases": {
            "large",
            "bge-large",
            "bge-large-zh-v1.5",
            "baai/bge-large-zh-v1.5",
        },
    },
}

_ALIAS_TO_KEY: dict[str, str] = {}
for _key, _spec in _MODEL_SPECS.items():
    _ALIASES = {str(a).strip().lower() for a in _spec.get("aliases", set())}
    _ALIASES.add(_key.lower())
    _ALIASES.add(str(_spec.get("repo_id") or "").strip().lower())
    for _alias in _ALIASES:
        if _alias:
            _ALIAS_TO_KEY[_alias] = _key


class NoopEmbeddingModel:
    def __init__(self, reason: str = "embedding 模型已禁用") -> None:
        self._reason = reason

    def name(self) -> str:
        return "noop"

    def is_available(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return self._reason

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError(self._reason or "embedding 模型不可用")


class LocalSentenceTransformerModel:
    """
    Lazy local model adapter.
    - 不在导入时强依赖 sentence-transformers。
    - 支持 small/base/large 三个本地 BGE 模型目录。
    - 已知模型优先走本地目录；未下载时给出明确不可用原因。
    """

    def __init__(self, model_hint: str = "") -> None:
        self._model_hint = model_hint.strip()
        self._backend = None
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
        return self._name or "sentence-transformers"

    def is_available(self) -> bool:
        self._ensure_loaded()
        return self._backend is not None

    def unavailable_reason(self) -> str:
        self._ensure_loaded()
        return self._reason

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._ensure_loaded()
        if self._backend is None:
            raise RuntimeError(self._reason or "embedding 模型不可用")
        if not texts:
            return []
        vectors = self._backend.encode(  # type: ignore[union-attr]
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        if hasattr(vectors, "tolist"):
            data = vectors.tolist()  # type: ignore[assignment]
        else:
            data = vectors
        return [[float(v) for v in row] for row in data]

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._loaded = True

            model_ref = self._resolve_model_ref()
            if not model_ref:
                return

            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
            except Exception as exc:
                self._reason = f"未安装 sentence-transformers: {exc}"
                return

            try:
                self._backend = SentenceTransformer(model_ref)
                if not self._name:
                    self._name = f"sentence-transformers:{model_ref}"
            except Exception as exc:
                self._backend = None
                self._reason = f"模型加载失败 '{model_ref}': {exc}"

    def _resolve_model_ref(self) -> Optional[str]:
        root = self._project_root()
        requested = self._model_hint or os.environ.get("MM_EMBEDDING_MODEL", "").strip()

        if not requested:
            requested = self._default_model_key(root)

        key = _ALIAS_TO_KEY.get(requested.strip().lower())
        if key:
            local_dir = self._resolve_local_model_dir(root / "tools" / "models" / key, root)
            if local_dir is None:
                self._reason = (
                    f"未找到本地模型：{key}。请放在 tools/models/{key} 目录下。"
                )
                self._name = key
                return None
            self._name = key
            return str(local_dir)

        local_dir = self._resolve_local_model_dir(requested, root)
        if local_dir is not None:
            self._name = f"local:{local_dir.name}"
            return str(local_dir)

        # 非已知模型标识：允许用户传入 HuggingFace repo id。
        if "/" in requested:
            self._name = requested
            return requested

        self._reason = f"未知模型标识：{requested}"
        return None

    @classmethod
    def _default_model_key(cls, root: Path) -> str:
        for key in ("bge-small-zh-v1.5", "bge-base-zh-v1.5", "bge-large-zh-v1.5"):
            if cls._resolve_local_model_dir(root / "tools" / "models" / key, root) is not None:
                return key
        return "bge-small-zh-v1.5"

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
        return True

    @staticmethod
    def _project_root(explicit_root: Optional[Path] = None) -> Path:
        if explicit_root is not None:
            return explicit_root
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]
