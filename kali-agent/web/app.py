from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.agent import create_kali_agent


BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

app = FastAPI(title="Kali Agent Web UI", version="0.1.0")

# 在应用启动时创建一次 Agent，避免重复加载 LLM/Prompt
agent = create_kali_agent()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """展示首页表单。"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "goal": "",
            "target": "",
            "nmap_arguments": "-sV -Pn",
            "result": None,
        },
    )


@app.post("/", response_class=HTMLResponse)
def run_scan(
    request: Request,
    goal: str = Form(..., description="渗透目标描述"),
    target: str = Form(..., description="扫描目标 IP/网段"),
    nmap_arguments: str = Form("-sV -Pn", description="Nmap 参数"),
) -> HTMLResponse:
    """处理表单提交，调用 Kali Agent 并展示 HUMAN_CHECK 结果。"""

    goal = goal.strip()
    target = target.strip()
    nmap_arguments = (nmap_arguments or "-sV -Pn").strip() or "-sV -Pn"

    error: str | None = None
    final_state: dict | None = None

    if not goal:
        error = "Goal 不能为空，请描述你的渗透目标。"
    elif not target:
        error = "Target 不能为空，请提供要扫描的 IP 或网段。"
    else:
        try:
            final_state = agent.invoke(
                {
                    "goal": goal,
                    "target": target,
                    "nmap_arguments": nmap_arguments,
                }
            )
        except Exception as exc:  # noqa: BLE001
            error = f"执行 Agent 时发生错误：{exc}"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "goal": goal,
            "target": target,
            "nmap_arguments": nmap_arguments,
            "result": final_state,
            "error": error,
        },
    )


__all__ = ["app"]

