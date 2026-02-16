# YOUKAI

基于 LLM 的红队辅助 Agent，带 Kali 风格 Web 控制台：与 Youkai 对话下发指令，流式查看侦察 / 分析 / 执行进度与 Nmap 实时输出，审阅报告后在一键确认窗口执行渗透（如 sqlmap）。

支持多种 LLM（OpenAI / Anthropic / Gemini / DeepSeek），默认在本机执行（无需 Docker），到手即用：启动后在「设置」里选模型、填 API Key 即可。

---

## 功能概览

- **与 Youkai 对话**：在对话窗口输入目标与指令（如「扫描 192.168.1.1」「攻击 http://target/page?id=1」），Youkai 先简短回复，再流式推进任务。
- **流式进度**：任务条与进度条实时显示 START → RECON → ANALYSIS → DECISION → HUMAN_CHECK；等待期间每 12 秒推送「进行中」，避免长时间无反馈。
- **Nmap 实时输出**：侦察阶段在本机执行 Nmap 时，终端会逐行显示扫描输出，可直接看到 Youkai 在做什么。
- **多终端各司其职**：侦察 / 分析 / 执行 / 总览 四个终端窗口，对应不同阶段输出与 DEBUG 信息。
- **报告与可视化**：Youkai 报告支持 Markdown；端口统计以饼图展示；摘要与任务列表在顶部展示。
- **确认执行**：单独「确认执行」窗口内填写利用 URL，审阅报告后点击「确认执行 (sqlmap)」执行渗透，结果在「终端 — 执行」中查看。
- **Kali 工具**：集成 nmap、nikto、dirb、gobuster、hydra、whatweb、searchsploit、whois 等，在工具窗口填写参数即可运行。
- **配置在 Web 完成**：LLM 提供商与 API Key、沙箱模式（本机 / Docker）均在「设置」中保存，无需改环境变量或重启。

---

## 快速开始

### 一条龙安装并启动（推荐）

```bash
chmod +x install_and_run.sh
./install_and_run.sh
```

浏览器打开 **http://127.0.0.1:8000** → **设置** → 选择 LLM（推荐 DeepSeek / Gemini）→ 填写 API Key → 保存，即可在首页与 Youkai 对话并下发扫描指令。

若尚未克隆仓库，可传入仓库地址由脚本先克隆再安装并启动：

```bash
./install_and_run.sh https://github.com/你的用户名/youkai.git
```

### 仅启动（已安装依赖）

日常使用若已安装过依赖，只需启动服务：

```bash
./run.sh
```

或：

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

### 手动安装

```bash
git clone <仓库地址>
cd youkai
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

---

## Web 界面说明

- **与 Youkai 对话**：左下角对话窗口输入指令并发送；Youkai 的简短回复与错误提示会显示在对话中，长结果在报告与终端中查看。
- **顶部**：任务步骤（START / RECON / ANALYSIS / DECISION / HUMAN_CHECK）、矩阵风格进度条、面板快捷按钮（对话 / 侦察 / 分析 / 执行 / 总览 / 报告 / 端口 / 本机 / 目标 / 跟踪 / 工具 / 确认）、设置入口。任务完成后会出现摘要卡片与端口饼图。
- **弹窗**：本机性能、目标情况、目标端口、实施跟踪、Youkai 报告、确认执行、终端（侦察 / 分析 / 执行 / 总览）、Kali 工具等窗口按需弹出，位置为层叠式（类似 Windows 自然叠放），可拖动、缩放、关闭/最小化/最大化。
- **确认执行**：在「确认执行」窗口填写目标 URL，点击「确认执行 (sqlmap)」执行 SQL 注入探测，输出在「终端 — 执行」中查看。

---

## 配置

- **在 Web 设置中**：选择 LLM 提供商、填写对应 API Key、选择沙箱模式（本机 / Docker）。配置保存在项目目录下 `config/runtime_settings.json`，不提交 Git。
- **环境变量（可选）**：若不想用 Web 保存的配置，可设置例如 `KALI_AGENT_DEEPSEEK_API_KEY`、`KALI_AGENT_SANDBOX_MODE=local` 等（前缀 `KALI_AGENT_`），详见 `config/settings.py`。

---

## 运行逻辑（Youkai 系统是怎么跑的）

### 整体流程

1. **用户在 Web 里发指令**  
   在「与 Youkai 对话」窗口输入一句话（如「扫描 192.168.1.1」或「攻击 http://target/page?id=1」），前端把这条消息 `POST` 到 `/api/command_stream`。

2. **后端解析并启动流式任务**  
   - 从消息里解析出 **目标**（IP/域名）、**目标描述**（goal）、**Nmap 参数**（默认 `-sV -Pn` 等）。  
   - 先往流里推一条 **`reply`**（如「收到，开始侦察目标…」），前端在对话里显示 Youkai 的简短回复。  
   - 再推一条 **`thinking`**（如「正在启动侦察（即将执行 Nmap）…」），让用户知道已经开始干活。  
   - 在一个**子线程**里启动 **LangGraph Agent**，主线程用 `asyncio.Queue` 收结果并往 HTTP 流里写。

3. **Agent 状态机（LangGraph）**  
   Agent 是一个固定流程的状态图，**顺序执行**，不分支、不循环：

   - **START**：校验并带上用户给的 goal、target、nmap_arguments。  
   - **RECON**：在沙箱里跑 **Nmap**（本机 subprocess 或 Docker）。扫描过程中，Nmap 的 **stdout 逐行**通过 `progress_line` 推到前端，前端在「终端 — 侦察」里流式显示。  
   - **ANALYSIS**：把 Nmap 结果 + 用户目标塞给 **LLM**，让 LLM 做「红队式分析」（开放端口、风险点、建议下一步）。  
   - **DECISION**：再调一次 LLM，根据分析结果输出一个 **JSON 决策**（path、reason、dangerous 等）。  
   - **HUMAN_CHECK**：把侦察摘要、分析、决策拼成一段 **人工确认报告**，写入状态里的 `human_check_message`，流程结束。**当前版本不会自动执行任何攻击**，只生成报告。

   每**完成一个节点**，子线程就往队列里放一个 **`step`**（节点名 + 文案），主线程转成 **`thinking`** 推给前端，用于任务条、进度条和终端 DEBUG。

4. **等待时的「进行中」**  
   若某个节点耗时很长（例如 Nmap 扫大网段），主线程用 **12 秒** 超时等队列：超时则往流里推一条「进行中，请稍候…」，再继续等，避免用户以为卡死。总等待超过 **5 分钟** 才报「执行超时」。

5. **任务结束后的输出**  
   - 把最终状态交给 **build_panels** 生成本机性能、目标、端口、跟踪、报告、摘要、端口饼图等数据。  
   - 把最终状态交给 **build_terminal_lines** 生成终端行（带 channel：recon/analysis/exec/general）。  
   - 后端**逐行**推送 **`terminal_line`**，前端在对应终端里流式追加并自动滚到底部。  
   - 最后推一条 **`done`**（只带 panels），前端更新各数据窗口、摘要、饼图，并在对话里说「分析完成，请查看报告与终端」。

6. **人工确认与利用**  
   用户在看「Youkai 报告」和终端后，若决定执行利用：  
   - 在「确认执行」窗口填 **目标 URL**，点「确认执行 (sqlmap)」。  
   - 前端请求 **`/api/execute_exploit`**，后端在沙箱里跑 **sqlmap**，结果以终端行的形式返回，前端在「终端 — 执行」里显示。  

   **Kali 工具**窗口里的 nmap、nikto、dirb 等是**独立接口**：填参数、点运行，直接调 `/api/tool`，不经过 Agent 状态机，结果同样在终端里展示。

### 数据流小结

- **请求**：用户一句话 → 解析 (goal, target, nmap_args) → 子线程跑 Agent 图。  
- **流式事件**：`reply` → `thinking`（可能多次 + 12 秒心跳）→ Nmap 期间的 `progress`（逐行）→ 各节点完成时的 `thinking` → 结束前的 `terminal_line`（逐行）→ `done`（panels）。  
- **前端**：按事件类型更新对话、任务条、进度条、四个终端、报告/本机/目标/端口等窗口；终端支持「回到底部」和实时跟踪。

---

## 项目结构

```text
youkai/
├── install_and_run.sh   # 一条龙：克隆（可选）→ 安装 → 启动
├── run.sh               # 仅启动（不安装、不克隆）
├── main.py              # CLI 入口
├── requirements.txt
├── config/
│   ├── settings.py      # 环境变量与默认配置
│   └── runtime.py       # Web 保存的运行时配置
├── core/
│   ├── agent.py         # LangGraph 状态机与 LLM 调用
│   └── sandbox.py       # 本机 / Docker 沙箱，支持 Nmap 实时输出
├── tools/
│   ├── scanning.py      # Nmap 扫描（含流式输出）
│   ├── exploitation.py  # sqlmap 等利用
│   └── kali_tools.py    # nmap / nikto / dirb / hydra 等封装
├── web/
│   ├── app.py           # FastAPI 应用与流式 API
│   ├── api_handlers.py  # 面板构建、终端行、解析等
│   └── templates/       # 前端页面（Kali 风格多窗口）
└── prompts/
    └── system_prompt.txt # 红队系统提示词
```

---

## 技术栈

- **后端**：Python 3、FastAPI、LangGraph、LangChain（OpenAI / Anthropic / Gemini / DeepSeek）
- **前端**：Tailwind CSS、Marked（Markdown）、Chart.js（饼图）、原生 JS（多窗口、流式 NDJSON）
- **沙箱**：本机 subprocess（默认）或 Docker 容器执行 Nmap 等命令

---

## 许可证与免责声明

本项目仅供授权测试与学习使用。使用者需自行确保对目标拥有合法授权，任何未授权访问或攻击行为与项目作者无关。
