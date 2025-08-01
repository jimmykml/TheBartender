import os
from anthropic import Anthropic, AsyncAnthropic
from models.base_model import BaseLLM

class ClaudeModel(BaseLLM):
    def __init__(self, model: str = "claude-3-opus-20240229", temperature: float = 0.7):
        self.model = model
        self.temperature = temperature
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def generate(self, prompt: str, **kwargs) -> str:
        # Claude requires a "messages" style interface, similar to OpenAI's newer APIs
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=self.temperature,
            messages=[
                {"role": "user", "content": prompt}
            ],
            **kwargs
        )
        return response.content[0].text.strip()
