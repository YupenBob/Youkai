from __future__ import annotations

"""Kali Agent 的 LangGraph 状态机实现。

状态流转：

- START: 接收用户目标与扫描参数
- RECON: 调用 Nmap 等侦察工具
- ANALYSIS: 使用 LLM 分析扫描结果
- DECISION: 使用 LLM 结合红队思维做下一步决策
- HUMAN_CHECK: 在执行任何潜在攻击性操作前，生成计划并停在此节点等待人工确认
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from config.settings import settings
from tools.scanning import nmap_scan


BASE_DIR = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "system_prompt.txt"


def _load_system_prompt() -> str:
    try:
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        # 兜底：如果文件不存在，使用一个简单的默认 Prompt
        return (
            "你是经验丰富的红队专家，擅长使用 Kali Linux 进行信息收集与安全分析。"
            "在任何可能造成破坏的操作前，必须先给出详细计划并请求人工确认。"
        )


SYSTEM_PROMPT = _load_system_prompt()


class KaliAgentState(TypedDict, total=False):
    """Agent 在 LangGraph 中使用的状态结构。"""

    # 用户输入
    goal: str
    target: str
    nmap_arguments: str

    # 中间结果
    recon_result: str
    analysis: str
    decision: str

    # 输出给人类审阅的说明
    human_check_message: str


def create_llm() -> BaseChatModel:
    """根据环境变量选择 OpenAI 或 Anthropic 作为 LLM。"""
    if settings.openai_api_key:
        return ChatOpenAI(model="gpt-4o", temperature=0.2)
    if settings.anthropic_api_key:
        # 具体模型名称可按需调整
        return ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0.2)

    raise RuntimeError(
        "未检测到可用的 LLM API Key。"
        "请在环境变量中配置 KALI_AGENT_OPENAI_API_KEY 或 KALI_AGENT_ANTHROPIC_API_KEY。"
    )


def build_kali_agent_graph(llm: BaseChatModel):
    """构建 Kali Agent 的 LangGraph 状态机并返回编译后的图对象。"""

    workflow = StateGraph(KaliAgentState)

    # --- 节点定义 ---

    def start_node(state: KaliAgentState) -> KaliAgentState:
        """START: 接收用户目标与扫描参数（这里主要是做规范化与日志）。"""
        goal = state.get("goal", "").strip()
        target = state.get("target", "").strip()
        nmap_args = state.get("nmap_arguments", "").strip() or "-sV -Pn"

        if not goal:
            raise ValueError("Agent 启动需要提供 goal（例：扫描 192.168.1.1 的常见服务）")
        if not target:
            raise ValueError("Agent 启动需要提供 target（例：192.168.1.1 或 10.0.0.0/24）")

        return {
            "goal": goal,
            "target": target,
            "nmap_arguments": nmap_args,
        }

    def recon_node(state: KaliAgentState) -> KaliAgentState:
        """RECON: 通过 Nmap 扫描目标，获取基础端口与服务信息。"""
        target = state["target"]
        nmap_arguments = state["nmap_arguments"]

        recon_text = nmap_scan.invoke(
            {
                "target": target,
                "arguments": nmap_arguments,
            }
        )

        return {
            "recon_result": recon_text,
        }

    def analysis_node(state: KaliAgentState) -> KaliAgentState:
        """ANALYSIS: 使用 LLM 分析 Nmap 结果。"""
        recon_result = state["recon_result"]
        goal = state["goal"]

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    "下面是一次针对渗透目标的 Nmap 扫描结果，请以红队专家的角度进行分析：\n\n"
                    f"用户目标 (Goal): {goal}\n\n"
                    "=== Nmap 输出开始 ===\n"
                    f"{recon_result}\n"
                    "=== Nmap 输出结束 ===\n\n"
                    "请完成以下任务：\n"
                    "1. 总结当前已知的开放端口与对应服务（如果有的话）。\n"
                    "2. 指出可能存在的高价值攻击面或潜在风险。\n"
                    "3. 结合红队流程，给出建议的下一步方向（例如 Web 枚举、SMB 枚举等）。\n"
                )
            ),
        ]

        resp = llm.invoke(messages)
        analysis_text = resp.content if isinstance(resp.content, str) else str(resp.content)

        return {
            "analysis": analysis_text,
        }

    def decision_node(state: KaliAgentState) -> KaliAgentState:
        """DECISION: 让 LLM 输出结构化的下一步决策，并标记是否需要危险动作。

        输出 JSON，例如：
        {
          "path": "web",
          "reason": "...",
          "dangerous": true
        }
        """
        analysis = state["analysis"]
        goal = state["goal"]

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    "基于以下分析结果，请给出下一步红队行动的决策。\n\n"
                    f"用户目标 (Goal): {goal}\n\n"
                    "=== 分析结果 ===\n"
                    f"{analysis}\n"
                    "================\n\n"
                    "请仅输出一个 JSON，对象格式如下（不要添加多余解释）：\n"
                    "{\n"
                    '  \"path\": \"web\" | \"smb\" | \"other\",  // 主要行动方向\n'
                    '  \"reason\": \"string\",                  // 为什么做这个选择\n'
                    '  \"dangerous\": true/false                // 是否包含潜在攻击性或高危操作\n'
                    "}\n"
                )
            ),
        ]

        resp = llm.invoke(messages)
        raw = resp.content if isinstance(resp.content, str) else str(resp.content)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 容错：如果解析失败，就包装成文本
            data = {
                "path": "other",
                "reason": f"LLM 返回的非 JSON 内容：{raw}",
                "dangerous": True,
            }

        pretty_decision = json.dumps(data, ensure_ascii=False, indent=2)
        return {
            "decision": pretty_decision,
        }

    def human_check_node(state: KaliAgentState) -> KaliAgentState:
        """HUMAN_CHECK: 在执行攻击性操作前，生成给人类看的计划说明并结束流程。

        当前版本不会真正调用 exploitation 工具，只是汇总信息并强调需要人工确认。
        """
        goal = state["goal"]
        target = state["target"]
        recon_result = state["recon_result"]
        analysis = state["analysis"]
        decision = state["decision"]

        message = (
            "[HUMAN_CHECK] 即将进入潜在攻击性或高危步骤，必须进行人工确认。\n\n"
            f"- 用户目标: {goal}\n"
            f"- 扫描目标: {target}\n\n"
            "=== 侦察结果（摘要） ===\n"
            f"{recon_result}\n\n"
            "=== 分析结果 ===\n"
            f"{analysis}\n\n"
            "=== 决策(JSON) ===\n"
            f"{decision}\n\n"
            "请人工审阅以上信息后，再决定是否允许执行具体 Exploit 或写入/提权等操作。\n"
            "当前版本不会自动执行任何 [DANGEROUS] 行为。"
        )

        return {
            "human_check_message": message,
        }

    # --- 将节点加入图 ---

    workflow.add_node("START", start_node)
    workflow.add_node("RECON", recon_node)
    workflow.add_node("ANALYSIS", analysis_node)
    workflow.add_node("DECISION", decision_node)
    workflow.add_node("HUMAN_CHECK", human_check_node)

    workflow.set_entry_point("START")

    workflow.add_edge("START", "RECON")
    workflow.add_edge("RECON", "ANALYSIS")
    workflow.add_edge("ANALYSIS", "DECISION")
    workflow.add_edge("DECISION", "HUMAN_CHECK")
    workflow.add_edge("HUMAN_CHECK", END)

    return workflow.compile()


def create_kali_agent():
    """对外暴露的帮助函数：创建一个可直接 .invoke(...) 的 Agent 图。

    使用方式示例：

    graph = create_kali_agent()
    final_state = graph.invoke(
        {
            "goal": "扫描 192.168.1.1 并给出下一步红队建议",
            "target": "192.168.1.1",
            "nmap_arguments": "-sV -Pn -p 1-1000",
        }
    )
    print(final_state["human_check_message"])
    """

    llm = create_llm()
    return build_kali_agent_graph(llm)


__all__ = ["KaliAgentState", "create_kali_agent", "create_llm", "build_kali_agent_graph"]

