from agents.base_agent import BaseAgent
from models.outputs import RecommendationAnalysis, ScoreComponent
from prompts.recommendation_agent_prompts import SYSTEM


class RecommendationAgent(BaseAgent[RecommendationAnalysis]):

    @property
    def output_type(self) -> type[RecommendationAnalysis]:
        return RecommendationAnalysis

    @property
    def system_prompt(self) -> str:
        return SYSTEM

    async def run_from_inputs(  # type: ignore[override]
        self,
        ticker: str,
        context: str,
        scores: list[ScoreComponent],
        composite_score: float,
    ) -> RecommendationAnalysis:
        prompt = (
            f"Produce an investment recommendation for {ticker.upper()} "
            f"using only the research context and deterministic scores below.\n\n{context}"
        )
        result = await self.run(prompt)
        # Overwrite with deterministic values so the LLM cannot drift from computed scores
        result.composite_score = composite_score
        result.scores = scores
        return result
