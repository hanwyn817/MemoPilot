from __future__ import annotations

from openai import OpenAI

from memopilot.config import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        if not settings.api_key:
            raise RuntimeError("未配置 OPENAI_API_KEY。")
        self.settings = settings
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)

    def generate(self, messages: list[dict[str, str]]) -> str:
        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=messages,
            temperature=0.2,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        return response.choices[0].message.content or ""

