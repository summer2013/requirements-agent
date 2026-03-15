"""
agent.py — 核心 agentic loop
支持任意智能体运行，工具处理通过回调注入，与具体业务解耦。

用法：
    result = run_agent(
        agent_name="research",
        system_prompt=open("prompts/research_system.txt").read(),
        tools=RESEARCH_TOOLS,
        model="claude-sonnet-4-6",
        tool_handler=my_handler,
        initial_message="请开始访谈...",
        history=[],          # 传入已有历史可继续上次对话
    )
"""

import os
import anthropic
from typing import Callable

# OpenRouter 和 Anthropic 直接 API 二选一
# 使用 OpenRouter：设置 OPENROUTER_API_KEY，模型名加 "anthropic/" 前缀
# 使用 Anthropic：设置 ANTHROPIC_API_KEY，模型名直接用原名
_openrouter_key = os.environ.get("OPENROUTER_API_KEY")
_anthropic_key  = os.environ.get("ANTHROPIC_API_KEY")

if _openrouter_key:
    client = anthropic.Anthropic(
        base_url="https://openrouter.ai/api/v1",
        api_key=_openrouter_key,
    )
elif _anthropic_key:
    client = anthropic.Anthropic(api_key=_anthropic_key)
else:
    raise EnvironmentError(
        "未找到 API Key。\n"
        "请在 .env 文件中配置 ANTHROPIC_API_KEY 或 OPENROUTER_API_KEY。\n"
        "参考 .env.example 文件。"
    )


def run_agent(
    agent_name: str,
    system_prompt: str,
    tools: list[dict],
    tool_handler: Callable[[str, dict], str],
    initial_message: str = "",
    history: list[dict] = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    on_tool_call: Callable[[str, dict], None] = None,
) -> tuple[str, list[dict]]:
    """
    运行单个智能体，支持多轮工具调用（agentic loop）。

    参数：
        agent_name      智能体名称（仅用于日志）
        system_prompt   System Prompt 文本
        tools           工具定义列表
        tool_handler    工具处理回调，签名：(tool_name, tool_input) -> str
        initial_message 第一条用户消息（history 为空时使用）
        history         已有消息历史，传入可继续上次对话（用于修订）
        model           模型名称
        max_tokens      最大输出 token 数
        temperature     温度
        on_tool_call    工具调用前的回调（用于日志/UI 更新）

    返回：
        (final_text, updated_history)
        final_text      智能体最终的文本输出
        updated_history 更新后的完整消息历史（用于下次继续）
    """
    msgs = list(history) if history else []

    # 初始消息
    if not msgs and initial_message:
        msgs.append({"role": "user", "content": initial_message})

    print(f"\n[{agent_name}] 启动")

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            tools=tools,
            messages=msgs,
        )

        # 追加助手回复
        msgs.append({"role": "assistant", "content": response.content})

        # 模型停止调用工具 → 返回最终文本
        if response.stop_reason == "end_turn":
            final_text = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            print(f"[{agent_name}] 完成")
            return final_text, msgs

        # 处理工具调用
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if on_tool_call:
                        on_tool_call(block.name, block.input)
                    print(f"  [{agent_name}] 工具调用: {block.name}")
                    result = tool_handler(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            msgs.append({"role": "user", "content": tool_results})
