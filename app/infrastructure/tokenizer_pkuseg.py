from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path


class NoopTokenizer:
    def __init__(self, reason: str = "分词器已禁用") -> None:
        self._reason = reason

    def name(self) -> str:
        return "noop-tokenizer"

    def is_available(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return self._reason

    def tokenize(self, text: str) -> list[str]:
        raise RuntimeError(self._reason or "分词器不可用")


class PkusegTokenizer:
    def __init__(self, user_dict: str = "") -> None:
        self._user_dict = user_dict.strip() or os.environ.get(
            "MM_PKUSEG_USER_DICT", ""
        ).strip()
        self._wheel_dir = os.environ.get("MM_PKUSEG_WHEEL_DIR", "").strip()
        self._vendor_dir = os.environ.get("MM_PKUSEG_VENDOR_DIR", "").strip()
        self._backend = None
        self._lock = threading.Lock()
        self._loaded = False
        self._name = "pkuseg"
        self._reason = ""

    def name(self) -> str:
        self._ensure_loaded()
        return self._name

    def is_available(self) -> bool:
        self._ensure_loaded()
        return self._backend is not None

    def unavailable_reason(self) -> str:
        self._ensure_loaded()
        return self._reason

    def tokenize(self, text: str) -> list[str]:
        self._ensure_loaded()
        if self._backend is None:
            raise RuntimeError(self._reason or "分词器不可用")
        source = str(text or "").strip()
        if not source:
            return []
        tokens = self._backend.cut(source)  # type: ignore[union-attr]
        return [str(token).strip() for token in tokens if str(token).strip()]

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._loaded = True

            pkuseg_mod = self._import_pkuseg()
            if pkuseg_mod is None:
                bootstrap_ok, bootstrap_reason = self._bootstrap_from_local_wheels()
                if bootstrap_ok:
                    pkuseg_mod = self._import_pkuseg()
                if pkuseg_mod is None:
                    if bootstrap_reason:
                        self._reason = bootstrap_reason
                    else:
                        self._reason = "未安装 pkuseg"
                    return

            kwargs: dict[str, str] = {}
            if self._user_dict:
                user_dict_path = Path(self._user_dict)
                if not user_dict_path.exists():
                    self._reason = f"pkuseg 用户词典不存在: {user_dict_path}"
                    return
                kwargs["user_dict"] = str(user_dict_path)
                self._name = f"pkuseg:{user_dict_path.name}"

            try:
                self._backend = pkuseg_mod.pkuseg(**kwargs)
            except Exception as exc:
                self._backend = None
                self._reason = f"pkuseg 加载失败: {exc}"

    def _import_pkuseg(self):
        try:
            import pkuseg  # type: ignore

            return pkuseg
        except Exception:
            return None

    def _bootstrap_from_local_wheels(self) -> tuple[bool, str]:
        wheel_dir = self._resolve_wheel_dir()
        if wheel_dir is None:
            return (
                False,
                "未安装 pkuseg: No module named 'pkuseg'，且未找到本地 wheel 目录",
            )

        target_dir = self._resolve_vendor_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        self._prepend_sys_path(target_dir)

        # If vendored package already exists, retry import directly.
        if (target_dir / "pkuseg").exists():
            return (True, "")

        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheel_dir),
            "--target",
            str(target_dir),
            "pkuseg",
        ]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except Exception as exc:
            return (False, f"本地安装 pkuseg 失败: {exc}")

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return (False, f"本地安装 pkuseg 失败: {detail}")
        return (True, "")

    def _resolve_wheel_dir(self) -> Path | None:
        candidates: list[Path] = []
        if self._wheel_dir:
            candidates.append(Path(self._wheel_dir))
        project_root = Path(__file__).resolve().parents[2]
        candidates.append(project_root / "%temp%" / "pkuseg_wheels")
        candidates.append(project_root / "tmp" / "pkuseg_wheels")

        for candidate in candidates:
            try:
                if not candidate.exists() or not candidate.is_dir():
                    continue
            except Exception:
                continue
            has_pkuseg_wheel = any(candidate.glob("pkuseg-*.whl"))
            if has_pkuseg_wheel:
                return candidate
        return None

    def _resolve_vendor_dir(self) -> Path:
        if self._vendor_dir:
            return Path(self._vendor_dir)
        project_root = Path(__file__).resolve().parents[2]
        return project_root / ".mm_vendor" / "pkuseg"

    def _prepend_sys_path(self, path: Path) -> None:
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
