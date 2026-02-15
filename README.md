# YOUKAI

基于 LLM 的红队辅助 Agent，默认在**本机（如 Kali 虚拟机）**执行 Nmap 等工具，支持 Docker 沙箱可选。支持多种 LLM：OpenAI、Anthropic、Google Gemini、DeepSeek。

## 目录结构

```text
youkai/
├── main.py                # CLI 入口
├── core/
│   ├── agent.py           # LangGraph 状态机与多 LLM 接入
│   └── sandbox.py         # 本机 / Docker 沙箱
├── tools/
│   ├── base.py
│   ├── scanning.py        # Nmap Tool
│   └── exploitation.py    # 高危工具占位
├── config/
│   └── settings.py        # API Key、沙箱模式等
├── prompts/
│   └── system_prompt.txt
├── web/
│   ├── app.py             # FastAPI Web UI
│   └── templates/
│       └── index.html
└── requirements.txt
```

## 环境变量（前缀 KALI_AGENT_）

- **LLM（任选其一）**  
  - `KALI_AGENT_OPENAI_API_KEY`  
  - `KALI_AGENT_ANTHROPIC_API_KEY`  
  - `KALI_AGENT_GOOGLE_GEMINI_API_KEY`  
  - `KALI_AGENT_DEEPSEEK_API_KEY`
- **沙箱**  
  - `KALI_AGENT_SANDBOX_MODE`：`local`（默认，本机执行）/ `docker`

## 快速开始

1. 安装依赖：`pip install -r requirements.txt`
2. 配置至少一个 LLM Key（环境变量或项目根目录 `.env`）
3. 默认为本机模式，无需 Docker；若用 Docker 模式需安装 Docker 并设置 `KALI_AGENT_SANDBOX_MODE=docker`
4. 启动 Web UI：`uvicorn web.app:app --reload --host 0.0.0.0 --port 8000`  
   或 CLI：`python main.py`

## LLM 优先级

Agent 按以下顺序选用第一个已配置的 Key：**OpenAI → Anthropic → Gemini → DeepSeek**。
