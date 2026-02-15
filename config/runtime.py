"""Web UI 保存的运行时配置（API Key、沙箱模式等），存于本地 JSON，不提交 Git。"""

from __future__ import annotations

import json
from pathlib import Path

# 项目根目录
_ROOT = Path(__file__).resolve().parents[1]
_RUNTIME_FILE = _ROOT / "config" / "runtime_settings.json"


def load_runtime_settings() -> dict:
    """读取 Web UI 保存的配置。若文件不存在或为空则返回空 dict。"""
    if not _RUNTIME_FILE.exists():
        return {}
    try:
        raw = _RUNTIME_FILE.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_runtime_settings(data: dict) -> None:
    """保存配置到本地 JSON（仅包含 UI 需要的字段，不写明文 Key 到日志）。"""
    _RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    # 只保留允许的键
    allowed = {"llm_provider", "api_key", "sandbox_mode"}
    out = {k: v for k, v in data.items() if k in allowed and v is not None}
    _RUNTIME_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def get_effective_llm_config() -> tuple[str | None, str | None]:
    """返回 (llm_provider, api_key)。provider 为 openai / anthropic / gemini / deepseek。"""
    runtime = load_runtime_settings()
    provider = (runtime.get("llm_provider") or "").strip().lower()
    api_key = (runtime.get("api_key") or "").strip()
    if provider and api_key:
        return provider, api_key
    return None, None


def get_effective_sandbox_mode() -> str:
    """返回当前生效的沙箱模式：local 或 docker。"""
    from config.settings import settings
    runtime = load_runtime_settings()
    mode = (runtime.get("sandbox_mode") or "").strip().lower()
    if mode in ("local", "docker"):
        return mode
    return (settings.sandbox_mode or "local").strip().lower() or "local"
