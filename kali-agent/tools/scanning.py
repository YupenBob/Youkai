from __future__ import annotations

import shlex
from typing import Optional

from langchain_core.tools import tool

from core.sandbox import CommandTimeoutError, KaliSandbox


_sandbox = KaliSandbox()


def _build_nmap_command(target: str, arguments: Optional[str]) -> list[str]:
    if not target:
        raise ValueError("Nmap 扫描目标不能为空")

    args: list[str] = ["nmap"]
    if arguments:
        args.extend(shlex.split(arguments))
    args.append(target)
    return args


def _filter_nmap_output(raw: str) -> str:
    """对 Nmap 输出做简单过滤，突出开放端口等关键信息。"""
    lines = raw.splitlines()
    important: list[str] = []

    in_ports_section = False
    for line in lines:
        stripped = line.strip()
        # 端口表头
        if stripped.lower().startswith("port") and "state" in stripped.lower():
            in_ports_section = True
            important.append(stripped)
            continue

        if in_ports_section:
            # 简单匹配 open 端口行
            if "/tcp" in stripped or "/udp" in stripped:
                if "open" in stripped:
                    important.append(stripped)
            # 空行则认为端口段结束
            if not stripped:
                in_ports_section = False

    if not important:
        # 如果没解析出端口信息，回退返回前若干行原始输出
        return "\n".join(lines[:80])

    return "\n".join(important)


@tool("nmap_scan", return_direct=False)
def nmap_scan(target: str, arguments: str = "-sV -Pn") -> str:
    """在 Kali Docker 沙箱中运行 Nmap。

    参数:
        target: 目标 IP / 域名 / CIDR，例如 "192.168.1.1" 或 "10.0.0.0/24"
        arguments: 传递给 nmap 的附加参数，如 "-sV -Pn -p 1-1000"

    返回:
        经过简单过滤后的文本结果，重点展示开放端口信息。
    """
    cmd = _build_nmap_command(target, arguments)

    try:
        result = _sandbox.run(cmd, timeout=300)
    except CommandTimeoutError:
        return "Nmap 扫描在 300 秒内未完成，已被沙箱超时终止。请缩小扫描范围或调整参数后重试。"
    except Exception as exc:  # noqa: BLE001
        return f"Nmap 扫描执行失败: {exc}"

    if result.exit_code != 0:
        # 优先展示 stderr，其次 stdout
        error_text = result.stderr.strip() or result.stdout.strip()
        return f"Nmap 扫描返回非零退出码 ({result.exit_code})：\n{error_text}"

    return _filter_nmap_output(result.stdout)


__all__ = ["nmap_scan"]

