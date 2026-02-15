# YOUKAI

基于 LLM 的红队辅助 Agent，默认在**本机（如 Kali 虚拟机）**执行 Nmap，支持多种 LLM（OpenAI / Anthropic / Gemini / DeepSeek）。**到手即用**：启动 Web UI 后到「设置」里选模型、填 API Key 即可，无需改环境变量。

---

## 一条龙启动（推荐）

克隆后执行一条命令完成安装并启动 Web UI：

```bash
chmod +x install_and_run.sh
./install_and_run.sh
```

浏览器打开 **http://127.0.0.1:8000**，进入 **设置** → 选择 LLM（推荐 DeepSeek）→ 填写 API Key → 保存，即可在首页使用扫描。

若尚未克隆，可直接传入仓库地址（脚本会先克隆再安装并启动）：

```bash
./install_and_run.sh https://github.com/你的用户名/youkai.git
```

---

## 手动安装

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

同样先打开 Web 界面，在 **设置** 中配置 API Key 与运行方式（本机 / Docker）。

---

## 在 Web 里能改什么

- **LLM 模型**：OpenAI、Anthropic、Gemini、DeepSeek 任选一个，填对应 API Key。
- **运行方式**：本机执行（默认，无需 Docker）或 Docker 容器。

配置保存在本机 `config/runtime_settings.json`，不提交 Git；保存后下次请求自动生效，无需重启服务。

---

## 目录结构

```text
youkai/
├── install_and_run.sh     # 一条龙脚本
├── main.py                # CLI 入口
├── core/
│   ├── agent.py
│   └── sandbox.py
├── tools/
├── config/
│   └── settings.py
├── web/
│   ├── app.py
│   └── templates/
└── requirements.txt
```

环境变量（可选，与 Web 设置二选一）：`KALI_AGENT_OPENAI_API_KEY`、`KALI_AGENT_DEEPSEEK_API_KEY`、`KALI_AGENT_SANDBOX_MODE` 等，前缀 `KALI_AGENT_`。
