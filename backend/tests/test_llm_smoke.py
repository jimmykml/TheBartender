import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai import Agent
from models.outputs import NewsAnalysis
from prompts.news_agent_prompts import SYSTEM as SYSTEM_PROMPT


# --- unit: no real API calls ---

@pytest.mark.asyncio
async def test_news_agent_structure():
    """Agent returns a valid NewsAnalysis without hitting any API."""
    from agents.news_agent import NewsAgent
    agent = NewsAgent.__new__(NewsAgent)
    agent._agent = Agent(TestModel(), output_type=NewsAnalysis, system_prompt=SYSTEM_PROMPT)
    agent._last_usage = None

    result = await agent.run("Ticker: AAPL\n\nHeadlines:\n- Apple beats earnings")
    assert isinstance(result, NewsAnalysis)


@pytest.mark.asyncio
async def test_build_model_unknown_provider():
    from clients.llm import build_model
    with pytest.raises(ValueError, match="Unknown provider"):
        build_model(provider="fakeai", model_name="fake-1")


def test_provider_registry_known():
    from clients.provider_registry import get_provider, REGISTRY
    for name in REGISTRY:
        info = get_provider(name)
        assert info.default_model in info.models


# --- live: skipped unless API keys present ---

@pytest.mark.asyncio
async def test_live_openai_smoke():
    import os
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    from agents.news_agent import NewsAgent
    agent = NewsAgent(provider="openai", model="gpt-4o-mini")
    result = await agent.run_from_inputs(
        ticker="AAPL",
        headlines=["Apple reports record revenue", "iPhone sales up 15% YoY"],
    )
    assert result.ticker
    assert result.sentiment in ("bullish", "bearish", "neutral")
    assert 0.0 <= result.confidence <= 1.0
