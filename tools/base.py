from __future__ import annotations

"""工具基类与公共工具帮助函数。"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ToolMetadata:
    """用于给 Tool 附加安全与审计相关元信息。"""

    name: str
    description: str
    dangerous: bool = False
    human_approval_required: bool = False
    notes: Optional[str] = None


__all__ = ["ToolMetadata"]
