from pydantic_ai.models import Model
from app.config import get_settings
from clients.provider_registry import get_provider


def build_model(provider: str | None = None, model_name: str | None = None) -> Model:
    settings = get_settings()
    provider = provider or settings.default_provider
    get_provider(provider)  # validate provider exists

    model_name = model_name or settings.default_model

    match provider:
        case "openai":
            from pydantic_ai.models.openai import OpenAIModel
            from pydantic_ai.providers.openai import OpenAIProvider
            key = settings.openai_api_key
            if not key:
                raise RuntimeError("OPENAI_API_KEY not set")
            return OpenAIModel(model_name, provider=OpenAIProvider(api_key=key))

        case "anthropic":
            from pydantic_ai.models.anthropic import AnthropicModel
            from pydantic_ai.providers.anthropic import AnthropicProvider
            key = settings.anthropic_api_key
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            return AnthropicModel(model_name, provider=AnthropicProvider(api_key=key))

        case "google":
            from pydantic_ai.models.gemini import GeminiModel
            from pydantic_ai.providers.google import GoogleProvider
            key = settings.google_api_key
            if not key:
                raise RuntimeError("GOOGLE_API_KEY not set")
            return GeminiModel(model_name, provider=GoogleProvider(api_key=key))

        case _:
            raise ValueError(f"Provider '{provider}' not implemented in factory")
