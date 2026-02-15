from __future__ import annotations

"""YOUKAI / Kali Agent 项目入口。

当前入口提供一个简单的命令行交互：

1. 询问用户渗透测试目标（goal）
2. 询问实际扫描目标 IP/网段（target）
3. 可选自定义 Nmap 参数（默认: -sV -Pn）
4. 调用基于 LangGraph 的 Agent，自动完成 START/RECON/ANALYSIS/DECISION/HUMAN_CHECK 流程
5. 将最终的 human_check_message 打印到终端，供人工审阅
"""

from core.agent import create_kali_agent


def main() -> None:
    print("=== YOUKAI (LLM 驱动红队辅助) ===")
    goal = input("请输入渗透目标描述 (goal)：").strip()
    target = input("请输入扫描目标 IP/网段 (target，例如 192.168.1.1)：").strip()
    nmap_args = input("请输入 Nmap 参数（回车使用默认 -sV -Pn）：").strip() or "-sV -Pn"

    agent = create_kali_agent()

    print("\n[Agent] 正在执行 START -> RECON -> ANALYSIS -> DECISION -> HUMAN_CHECK 流程...\n")
    final_state = agent.invoke(
        {
            "goal": goal,
            "target": target,
            "nmap_arguments": nmap_args,
        }
    )

    message = final_state.get("human_check_message")
    if message:
        print("=== HUMAN_CHECK 输出 ===")
        print(message)
    else:
        print("Agent 执行完成，但未生成 human_check_message。最终状态如下：")
        print(final_state)


if __name__ == "__main__":
    main()
