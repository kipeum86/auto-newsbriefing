"""OpenAI GPT LLM provider."""

import json
import logging
import os

from openai import OpenAI

from pipeline.llm.base import LLMProvider

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = ""):
        self.model = model or DEFAULT_MODEL
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key)

    def complete(self, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    def complete_json(self, system: str, user: str, max_retries: int = 3) -> dict:
        """Use native JSON mode for OpenAI."""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                text = response.choices[0].message.content or "{}"
                return json.loads(text)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning("OpenAI JSON attempt %d failed: %s", attempt + 1, e)
                if attempt == max_retries - 1:
                    raise
        return {}
