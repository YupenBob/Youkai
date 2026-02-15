from __future__ import annotations

from pathlib import Path

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.runtime import load_runtime_settings, save_runtime_settings
from core.agent import create_kali_agent


BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

app = FastAPI(title="YOUKAI / Kali Agent Web UI", version="0.1.0")

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
