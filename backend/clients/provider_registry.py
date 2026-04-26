from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    env_key: str
    default_model: str
    models: tuple[str, ...]


REGISTRY: dict[str, ProviderInfo] = {
    "openai": ProviderInfo(
        env_key="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
        models=(
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "o1-mini",
        ),
    ),
    "anthropic": ProviderInfo(
        env_key="ANTHROPIC_API_KEY",
        default_model="claude-3-5-haiku-latest",
        models=(
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-3-5-haiku-latest",
        ),
    ),
    "google": ProviderInfo(
        env_key="GOOGLE_API_KEY",
        default_model="gemini-1.5-flash",
        models=(
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
        ),
    ),
}


def get_provider(name: str) -> ProviderInfo:
    if name not in REGISTRY:
        raise ValueError(f"Unknown provider '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[name]
