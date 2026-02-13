# Kali Agent

基于 LLM 的红队辅助 Agent，运行在沙箱化的 Kali Linux Docker 环境中，通过 ReAct / LangGraph 模式执行渗透测试相关任务（如端口扫描、服务识别、漏洞验证等）。

## 目录结构

```text
kali-agent/
├── main.py                # 项目入口，当前用于本地演示 Nmap 扫描
├── core/
│   ├── agent.py           # ReAct 循环与状态管理（占位，计划基于 LangGraph 实现）
│   └── sandbox.py         # Docker 容器交互逻辑（Kali 沙箱）
├── tools/
│   ├── base.py            # 工具元信息/基类
│   ├── scanning.py        # 封装 Nmap 扫描为 LangChain Tool
│   └── exploitation.py    # 高危利用类工具占位（需人工审批）
├── config/
│   └── settings.py        # API Keys 与 Docker 配置（Pydantic BaseSettings）
├── prompts/
│   └── system_prompt.txt  # 注入红队思维的核心 Prompt
└── requirements.txt       # Python 依赖
```

## 快速开始

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 确保本机已安装 Docker，并提前拉取 Kali 镜像：

```bash
docker pull kalilinux/kali-rolling
```

3. 运行简单 Nmap 演示（会在 Kali 容器中执行）：

```bash
python main.py
```

> 注意：当前仅实现了基础沙箱与 Nmap 扫描 Tool，完整的 LangGraph 状态机与 LLM 调用将在后续迭代中补充。

