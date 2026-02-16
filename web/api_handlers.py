"""API 逻辑：本机状态、终端流、指令解析。"""

from __future__ import annotations

import re
from typing import Any


def get_local_stats() -> dict[str, Any]:
    """本机性能/状态（CPU、内存等）。"""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": round(cpu, 1),
            "mem_percent": round(mem.percent, 1),
            "mem_used_gb": round(mem.used / (1024**3), 2),
            "mem_total_gb": round(mem.total / (1024**3), 2),
        }
    except Exception:
        return {"cpu_percent": 0, "mem_percent": 0, "mem_used_gb": 0, "mem_total_gb": 0}


def parse_goal_target_from_message(message: str) -> tuple[str, str, str]:
    """从自然语言指令中解析 goal、target、nmap_args。返回 (goal, target, nmap_arguments)。"""
    msg = (message or "").strip()
    if not msg:
        return "扫描并分析目标", "", "-sV -Pn"

    # 提取 IP / 域名 / CIDR
    ip4 = r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b"
    hostname = r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"
    target_match = re.search(ip4, msg) or re.search(hostname, msg)
    target = target_match.group(0) if target_match else ""

    # 若未识别到目标，尝试“扫描 xxx”中的 xxx
    if not target and "扫描" in msg:
        parts = msg.replace("扫描", " ").split()
        for p in parts:
            if re.match(ip4, p) or re.match(hostname, p):
                target = p
                break

    goal = msg if msg else "扫描并分析目标"
    nmap_args = "-sV -Pn"
    if "-p" in msg or "端口" in msg:
        nmap_args = "-sV -Pn -p 1-1000"
    return goal, target or "127.0.0.1", nmap_args


def build_terminal_lines(state: dict[str, Any]) -> list[dict[str, Any]]:
    """把 Agent 状态转成 Kali 风格多色终端行。type: cmd|info|success|warn|error；channel: recon|analysis|exec|general。"""
    lines: list[dict[str, Any]] = []
    lines.append({"type": "cmd", "text": "[YOUKAI] START → RECON → ANALYSIS → DECISION → HUMAN_CHECK", "channel": "general"})
    lines.append({"type": "info", "text": f"Goal: {state.get('goal', '')}", "channel": "general"})
    lines.append({"type": "info", "text": f"Target: {state.get('target', '')}", "channel": "general"})

    recon = state.get("recon_result") or ""
    if recon:
        for line in recon.splitlines()[:30]:
            line = line.strip()
            if not line:
                continue
            if "open" in line.lower() and ("tcp" in line or "udp" in line):
                lines.append({"type": "success", "text": line, "channel": "recon"})
            else:
                lines.append({"type": "info", "text": line, "channel": "recon"})

    analysis = state.get("analysis") or ""
    if analysis:
        lines.append({"type": "warn", "text": "--- LLM 分析 ---", "channel": "analysis"})
        for line in analysis.splitlines()[:15]:
            if line.strip():
                lines.append({"type": "info", "text": line.strip(), "channel": "analysis"})

    decision = state.get("decision") or ""
    if decision:
        lines.append({"type": "warn", "text": "--- 决策 ---", "channel": "exec"})
        lines.append({"type": "info", "text": decision.strip()[:500], "channel": "exec"})

    report = state.get("human_check_message") or ""
    if report:
        lines.append({"type": "success", "text": "[HUMAN_CHECK] 报告已生成，请审阅后点击「确认执行」。", "channel": "exec"})

    return lines


def _parse_port_counts(recon: str) -> dict[str, int]:
    """从 recon 文本中解析 open/filtered/closed 数量，供前端饼图使用。"""
    open_count = filtered_count = closed_count = 0
    for line in recon.splitlines():
        line_lower = line.lower()
        if "open" in line_lower and ("tcp" in line_lower or "udp" in line_lower):
            open_count += 1
        if "filtered" in line_lower:
            filtered_count += 1
        if "closed" in line_lower and ("tcp" in line_lower or "udp" in line_lower):
            closed_count += 1
    return {"open": open_count, "filtered": filtered_count, "closed": closed_count}


def _report_summary(report: str, max_lines: int = 5, max_chars: int = 400) -> str:
    """截取报告摘要，用于简洁展示。"""
    if not report:
        return ""
    lines = [ln.strip() for ln in report.splitlines() if ln.strip()][:max_lines]
    text = "\n".join(lines)
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def build_panels(state: dict[str, Any], local_stats: dict[str, Any]) -> dict[str, Any]:
    """组装数据窗口内容。含 port_counts（饼图）、report_summary（简洁展示）。"""
    recon = (state.get("recon_result") or "").strip()
    analysis = (state.get("analysis") or "").strip()
    decision = (state.get("decision") or "").strip()
    report = (state.get("human_check_message") or "").strip()
    full_report = report or analysis or "暂无报告"

    # 从 recon 里简单提取端口行
    port_lines = [l.strip() for l in recon.splitlines() if "open" in l.lower() and ("tcp" in l or "udp" in l)]
    port_counts = _parse_port_counts(recon)
    report_summary = _report_summary(full_report)

    return {
        "local_stats": local_stats,
        "target_info": {
            "goal": state.get("goal", ""),
            "target": state.get("target", ""),
        },
        "ports": "\n".join(port_lines) if port_lines else (recon[:800] if recon else "暂无"),
        "port_counts": port_counts,
        "tracking": f"目标: {state.get('target', '')}\n分析完成 → 决策已生成",
        "report": full_report,
        "report_summary": report_summary,
    }
