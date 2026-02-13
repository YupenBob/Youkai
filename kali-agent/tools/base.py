from __future__ import annotations

"""工具基类与公共工具帮助函数。

目前项目中主要依赖 LangChain 的 @tool 装饰器直接定义函数式工具，
后续如果需要更复杂的工具管理（如权限分级、审计日志），可以在这里扩展。
"""

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

