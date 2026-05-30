"""Agent dispatcher - the core tool call loop"""

import json

from xm.llm import LLM, Response
from xm.session import Session
from xm.tools import ToolRegistry


async def run(
    user_message: str,
    session: Session,
    llm: LLM,
    tools: ToolRegistry,
    system_prompt: str | None = None,
    verbose: bool = False,
) -> str:
    """Run the agent loop: send message, execute tools, return final response."""
    session.add_message("user", user_message)

    messages = session.get_messages()
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})

    tool_defs = tools.get_definitions()

    while True:
        response: Response = await llm.chat(messages=messages, tools=tool_defs or None)

        if verbose:
            print(f"[model] {response.model}")

        # Record assistant message
        tool_calls_data = None
        if response.tool_calls:
            tool_calls_data = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in response.tool_calls
            ]

        session.add_message(
            "assistant",
            content=response.content,
            tool_calls=tool_calls_data,
        )

        # No tool calls - we're done
        if not response.tool_calls:
            return response.content or ""

        # Execute tool calls
        for tc in response.tool_calls:
            if verbose:
                print(f"[tool] {tc.name}({tc.arguments})")

            result = await tools.execute(tc.name, tc.arguments)

            if verbose:
                preview = result[:200] + "..." if len(result) > 200 else result
                print(f"[result] {preview}")

            session.add_message(
                "tool",
                content=result,
                tool_call_id=tc.id,
            )

        # Continue loop - let model process tool results
        messages = session.get_messages()
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})
