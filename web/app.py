from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config.runtime import load_runtime_settings, save_runtime_settings
from core.agent import create_kali_agent
from tools.exploitation import run_dangerous_command
from tools.kali_tools import run_tool
from web.api_handlers import (
    build_panels,
    build_terminal_lines,
    get_local_stats,
    parse_goal_target_from_message,
)

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

app = FastAPI(title="YOUKAI / Kali Agent Web UI", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

_agent_cache = None


def get_agent():
    """懒加载 Agent，保存设置后下次请求会使用新配置。"""
    global _agent_cache
    if _agent_cache is not None:
        return _agent_cache
    _agent_cache = create_kali_agent()
    return _agent_cache


def clear_agent_cache():
    global _agent_cache
    _agent_cache = None


def has_llm_configured() -> bool:
    """是否已配置任一 LLM（Web 保存或环境变量）。"""
    from config.runtime import get_effective_llm_config
    from config.settings import settings
    provider, key = get_effective_llm_config()
    if provider and key:
        return True
    return bool(
        settings.openai_api_key
        or settings.anthropic_api_key
        or settings.google_gemini_api_key
        or settings.deepseek_api_key
    )


@app.post("/api/command")
async def api_command(request: Request) -> JSONResponse:
    """与 Youkai 对话：下发扫描/攻击指令，返回数据窗口与终端流。"""
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    except Exception:
        body = {}
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "请输入指令内容"},
        )
    if not has_llm_configured():
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "请先在「设置」中配置 LLM API Key"},
        )

    goal, target, nmap_arguments = parse_goal_target_from_message(message)
    if not target:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "未从指令中识别到目标 IP 或域名，请写明例如：扫描 192.168.1.1"},
        )

    try:
        agent = get_agent()
        state = agent.invoke(
            {"goal": goal, "target": target, "nmap_arguments": nmap_arguments}
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": str(exc),
                "panels": {"local_stats": get_local_stats(), "target_info": {}, "ports": "", "tracking": "", "report": ""},
                "terminal": [{"type": "error", "text": str(exc)}],
            },
        )

    local_stats = get_local_stats()
    panels = build_panels(state, local_stats)
    terminal = build_terminal_lines(state)
    return JSONResponse(
        content={
            "ok": True,
            "panels": panels,
            "terminal": terminal,
        },
    )


STEP_MESSAGES = {
    "START": "接收目标，准备侦察…",
    "RECON": "执行 Nmap 扫描中…",
    "ANALYSIS": "LLM 分析扫描结果中…",
    "DECISION": "生成下一步决策中…",
    "HUMAN_CHECK": "生成人工确认报告…",
}


async def _stream_command_events(goal: str, target: str, nmap_arguments: str):
    """异步生成器：逐步推送 Thinking 与最终结果（NDJSON 每行一个 JSON）。"""
    queue: asyncio.Queue = asyncio.Queue()
    final_state: dict | None = None
    error: str | None = None

    def run_stream():
        nonlocal final_state, error
        try:
            agent = get_agent()
            initial = {"goal": goal, "target": target, "nmap_arguments": nmap_arguments}
            state = dict(initial)
            try:
                for chunk in agent.stream(initial, stream_mode="updates"):
                    for node_name, update in chunk.items():
                        state = {**state, **update}
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            ("step", node_name, STEP_MESSAGES.get(node_name, node_name)),
                        )
            except Exception as e:  # noqa: BLE001
                error = str(e)
            final_state = state
        except Exception as e:  # noqa: BLE001
            error = str(e)
        loop.call_soon_threadsafe(queue.put_nowait, ("done",))

    loop = asyncio.get_event_loop()
    thread = threading.Thread(target=run_stream, daemon=True)
    thread.start()

    while True:
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=120.0)
        except asyncio.TimeoutError:
            yield json.dumps({"type": "error", "message": "执行超时"}, ensure_ascii=False) + "\n"
            break
        if msg[0] == "step":
            _, node_name, message = msg
            yield json.dumps(
                {"type": "thinking", "step": node_name, "message": message},
                ensure_ascii=False,
            ) + "\n"
        elif msg[0] == "done":
            if error:
                yield json.dumps({"type": "error", "message": error}, ensure_ascii=False) + "\n"
                break
            local_stats = get_local_stats()
            panels = build_panels(final_state or {}, local_stats)
            terminal = build_terminal_lines(final_state or {})
            yield json.dumps(
                {"type": "done", "ok": True, "panels": panels, "terminal": terminal},
                ensure_ascii=False,
            ) + "\n"
            break


@app.post("/api/command_stream")
async def api_command_stream(request: Request):
    """与 Youkai 对话（流式）：实时推送 Thinking 步骤与最终结果，响应为 NDJSON 流。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "无效 JSON"})
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse(status_code=400, content={"error": "请输入指令内容"})
    if not has_llm_configured():
        return JSONResponse(status_code=400, content={"error": "请先在「设置」中配置 LLM API Key"})
    goal, target, nmap_arguments = parse_goal_target_from_message(message)
    if not target:
        return JSONResponse(status_code=400, content={"error": "未从指令中识别到目标，请写明例如：扫描 192.168.1.1"})

    return StreamingResponse(
        _stream_command_events(goal, target, nmap_arguments),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/execute_exploit")
async def api_execute_exploit(request: Request) -> JSONResponse:
    """人工确认后执行利用（如 sqlmap）。请求体: {"action": "sqlmap", "url": "http://..."}。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "无效 JSON"})
    action = (body.get("action") or "").strip().lower()
    if action not in ("sqlmap",):
        return JSONResponse(status_code=400, content={"ok": False, "error": "仅支持 action: sqlmap"})
    payload = body.get("payload") or body
    code, out, err = run_dangerous_command(action, payload)
    terminal = [
        {"type": "cmd", "text": f"[EXPLOIT] {action} 已执行"},
        {"type": "error" if code != 0 else "success", "text": err or out or f"退出码 {code}"},
    ]
    for line in (out or "").splitlines()[:50]:
        if line.strip():
            terminal.append({"type": "info", "text": line.strip()})
    return JSONResponse(content={"ok": code == 0, "terminal": terminal, "exit_code": code})


# Kali 工具列表（供前端展示与调用）
KALI_TOOLS = [
    {"id": "nmap", "name": "Nmap", "desc": "端口/服务扫描", "params": [{"key": "target", "label": "目标", "placeholder": "192.168.1.1"}, {"key": "args", "label": "参数", "placeholder": "-sV -Pn"}]},
    {"id": "nikto", "name": "Nikto", "desc": "Web 服务器扫描", "params": [{"key": "url", "label": "URL", "placeholder": "http://target/"}]},
    {"id": "dirb", "name": "Dirb", "desc": "目录枚举", "params": [{"key": "url", "label": "URL", "placeholder": "http://target/"}]},
    {"id": "gobuster_dir", "name": "Gobuster Dir", "desc": "目录枚举", "params": [{"key": "url", "label": "URL", "placeholder": "http://target/"}]},
    {"id": "gobuster_dns", "name": "Gobuster DNS", "desc": "子域名枚举", "params": [{"key": "domain", "label": "域名", "placeholder": "example.com"}]},
    {"id": "whatweb", "name": "Whatweb", "desc": "Web 技术指纹", "params": [{"key": "url", "label": "URL", "placeholder": "http://target/"}]},
    {"id": "whois", "name": "Whois", "desc": "域名信息", "params": [{"key": "domain", "label": "域名", "placeholder": "example.com"}]},
    {"id": "ping", "name": "Ping", "desc": "连通性测试", "params": [{"key": "host", "label": "主机", "placeholder": "192.168.1.1"}]},
    {"id": "curl", "name": "Curl", "desc": "HTTP 请求", "params": [{"key": "url", "label": "URL", "placeholder": "http://target/"}, {"key": "method", "label": "方法", "placeholder": "GET"}]},
    {"id": "searchsploit", "name": "Searchsploit", "desc": "漏洞库搜索", "params": [{"key": "keyword", "label": "关键词", "placeholder": "apache 2.4"}]},
    {"id": "hydra", "name": "Hydra", "desc": "暴力破解", "params": [{"key": "target", "label": "目标", "placeholder": "192.168.1.1"}, {"key": "service", "label": "服务", "placeholder": "ssh"}, {"key": "user", "label": "用户", "placeholder": "root"}, {"key": "passlist", "label": "密码字典", "placeholder": "/usr/share/wordlists/rockyou.txt"}]},
]


@app.get("/api/tools")
def api_tools_list() -> JSONResponse:
    """返回 Kali 工具列表（名称、描述、参数定义）。"""
    return JSONResponse(content={"tools": KALI_TOOLS})


@app.post("/api/tool")
async def api_tool_run(request: Request) -> JSONResponse:
    """执行指定 Kali 工具，返回终端风格输出。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "无效 JSON"})
    tool_id = (body.get("tool") or body.get("id") or "").strip().lower()
    params = body.get("params") or {}
    if not tool_id:
        return JSONResponse(status_code=400, content={"ok": False, "error": "缺少 tool"})
    code, out, err = run_tool(tool_id, params)
    terminal = [
        {"type": "cmd", "text": f"[Kali] {tool_id} 执行"},
        {"type": "error" if code != 0 else "success", "text": (err or out or f"退出码 {code}")[:500]},
    ]
    for line in (out or "").splitlines()[:80]:
        if line.strip():
            terminal.append({"type": "info", "text": line.strip()})
    return JSONResponse(content={"ok": code == 0, "terminal": terminal, "exit_code": code})


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    need_settings = not has_llm_configured()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "goal": "",
            "target": "",
            "nmap_arguments": "-sV -Pn",
            "result": None,
            "need_settings": need_settings,
        },
    )


@app.post("/", response_class=HTMLResponse)
def run_scan(
    request: Request,
    goal: str = Form(..., description="渗透目标描述"),
    target: str = Form(..., description="扫描目标 IP/网段"),
    nmap_arguments: str = Form("-sV -Pn", description="Nmap 参数"),
) -> HTMLResponse:
    goal = goal.strip()
    target = target.strip()
    nmap_arguments = (nmap_arguments or "-sV -Pn").strip() or "-sV -Pn"
    error: str | None = None
    final_state: dict | None = None
    if not has_llm_configured():
        error = "请先在「设置」中配置 LLM API Key 后再使用扫描功能。"
    elif not goal:
        error = "Goal 不能为空，请描述你的渗透目标。"
    elif not target:
        error = "Target 不能为空，请提供要扫描的 IP 或网段。"
    else:
        try:
            agent = get_agent()
            final_state = agent.invoke(
                {"goal": goal, "target": target, "nmap_arguments": nmap_arguments}
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
            "need_settings": not has_llm_configured(),
        },
    )


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    runtime = load_runtime_settings()
    saved = request.query_params.get("ok") == "1"
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "llm_provider": runtime.get("llm_provider") or "deepseek",
            "api_key_placeholder": "留空则保留已保存的 Key，重新填写可覆盖",
            "sandbox_mode": runtime.get("sandbox_mode") or "local",
            "saved": saved,
        },
    )


@app.post("/settings", response_class=HTMLResponse)
def settings_save(
    request: Request,
    llm_provider: str = Form("deepseek"),
    api_key: str = Form(""),
    sandbox_mode: str = Form("local"),
) -> HTMLResponse:
    llm_provider = (llm_provider or "deepseek").strip().lower()
    if llm_provider not in ("openai", "anthropic", "gemini", "deepseek"):
        llm_provider = "deepseek"
    api_key = api_key.strip()
    sandbox_mode = (sandbox_mode or "local").strip().lower()
    if sandbox_mode not in ("local", "docker"):
        sandbox_mode = "local"

    runtime = load_runtime_settings()
    if api_key:
        runtime["api_key"] = api_key
    runtime["llm_provider"] = llm_provider
    runtime["sandbox_mode"] = sandbox_mode
    save_runtime_settings(runtime)
    clear_agent_cache()

    return RedirectResponse(url="/settings?ok=1", status_code=302)


__all__ = ["app"]
