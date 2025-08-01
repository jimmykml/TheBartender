import yaml

def load_model():
    with open("config/settings.yaml") as f:
        config = yaml.safe_load(f)

    provider = config["model_provider"]

    if provider == "openai":
        from models.openai_model import OpenAIModel
        return OpenAIModel(model=config["model"])
    elif provider == "claude":
        from models.claude_model import ClaudeModel
        return ClaudeModel(model=config["model"])
    elif provider == "google":
        from models.google_model import GoogleModel
        return GoogleModel(model=config["model"])
    else:
        raise ValueError(f"Unknown model provider: {provider}")
