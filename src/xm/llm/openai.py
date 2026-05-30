"""OpenAI LLM provider"""

import json

from openai import AsyncOpenAI

from xm.config import get_api_key, get_base_url
from xm.llm import LLM, Response, ToolCall


class OpenAILLM(LLM):
    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        api_key = get_api_key("openai")
        base_url = get_base_url("openai")
        kwargs = {}
        if base_url:
            kwargs["base_url"] = base_url
            # Local endpoints often don't need API keys
            if not api_key:
                api_key = "not-needed"
        kwargs["api_key"] = api_key or "not-needed"
        self.client = AsyncOpenAI(**kwargs)

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
    ) -> Response:
        kwargs = {
            "model": model or self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        resp = await self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        return Response(
            content=msg.content,
            tool_calls=tool_calls,
            model=resp.model,
        )
