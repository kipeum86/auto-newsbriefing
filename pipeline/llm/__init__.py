"""LLM provider factory."""

from pipeline.llm.base import LLMProvider


def create_provider(provider_name: str, model: str = "") -> LLMProvider:
    """Create LLM provider by name."""
    if provider_name == "claude":
        from pipeline.llm.claude import ClaudeProvider
        return ClaudeProvider(model)
    elif provider_name == "openai":
        from pipeline.llm.openai import OpenAIProvider
        return OpenAIProvider(model)
    elif provider_name == "gemini":
        from pipeline.llm.gemini import GeminiProvider
        return GeminiProvider(model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
