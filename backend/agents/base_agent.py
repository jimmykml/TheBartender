from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.usage import RunUsage

from app.config import get_settings
from clients.llm import build_model
from core.usage_tracker import UsageSummary, compute_cost

OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(ABC, Generic[OutputT]):
    """
    Abstract base for all PydanticAI agents.

    Subclasses must define:
      - output_type  : the Pydantic model class for structured output
      - system_prompt: the agent's system instructions

    Optional overrides:
      - tools        : list of tool functions to expose to the agent
      - build_prompt : format raw inputs into the user-facing prompt string
    """

    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._model_name: str = model or settings.default_model
        self._agent: Agent[None, OutputT] = Agent(
            build_model(provider, model),
            output_type=self.output_type,
            system_prompt=self.system_prompt,
            tools=self.tools,
        )
        self._last_usage: RunUsage | None = None

    # ── subclass contract ────────────────────────────────────────────────────

    @property
    @abstractmethod
    def output_type(self) -> type[OutputT]: ...

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    @property
    def tools(self) -> list:
        return []

    # ── public interface ─────────────────────────────────────────────────────

    async def run(self, prompt: str) -> OutputT:
        result = await self._agent.run(prompt)
        self._last_usage = result.usage()
        return result.output

    def usage(self) -> RunUsage | None:
        """Raw token counts from the most recent run."""
        return self._last_usage

    def compute_usage(self) -> UsageSummary | None:
        """Token usage + estimated cost for the most recent run."""
        if self._last_usage is None:
            return None
        return compute_cost(self._model_name, self._last_usage)

    # ── optional hook ────────────────────────────────────────────────────────

    def build_prompt(self, **kwargs: object) -> str:
        """
        Override to format structured inputs into a prompt string.
        By default raises NotImplementedError — either override this
        or call run() directly with a pre-built string.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement build_prompt() "
            "or call run() with a prompt string directly."
        )

    async def run_from_inputs(self, **kwargs: object) -> OutputT:
        """Convenience: build_prompt(**kwargs) then run()."""
        return await self.run(self.build_prompt(**kwargs))
