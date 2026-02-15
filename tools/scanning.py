from __future__ import annotations

import shlex
from typing import Optional

from langchain_core.tools import tool

from core.sandbox import CommandTimeoutError, get_sandbox


_sandbox = get_sandbox()


def _build_nmap_command(target: str, arguments: Optional[str]) -> list[str]:
    if not target:
        raise ValueError("Nmap 扫描目标不能为空")
    args: list[str] = ["nmap"]
    if arguments:
        args.extend(shlex.split(arguments))
    args.append(target)
    return args


def _filter_nmap_output(raw: str) -> str:
    lines = raw.splitlines()
    important: list[str] = []
    in_ports_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("port") and "state" in stripped.lower():
            in_ports_section = True
            important.append(stripped)
            continue
        if in_ports_section:
            if "/tcp" in stripped or "/udp" in stripped:
                if "open" in stripped:
                    important.append(stripped)
            if not stripped:
                in_ports_section = False
    if not important:
        return "\n".join(lines[:80])
    return "\n".join(important)


@tool("nmap_scan", return_direct=False)
def nmap_scan(target: str, arguments: str = "-sV -Pn") -> str:
    """在沙箱中运行 Nmap（默认本机，可由 KALI_AGENT_SANDBOX_MODE 切换 Docker）。"""
    cmd = _build_nmap_command(target, arguments)
    try:
        result = _sandbox.run(cmd, timeout=300)
    except CommandTimeoutError:
        return "Nmap 扫描在 300 秒内未完成，已被沙箱超时终止。请缩小扫描范围或调整参数后重试。"
    except Exception as exc:  # noqa: BLE001
        return f"Nmap 扫描执行失败: {exc}"
    if result.exit_code != 0:
        error_text = result.stderr.strip() or result.stdout.strip()
        return f"Nmap 扫描返回非零退出码 ({result.exit_code})：\n{error_text}"
    return _filter_nmap_output(result.stdout)


__all__ = ["nmap_scan"]
