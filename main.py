from models.openai_model import OpenAIModel
from core.agent_orchestrator import AgentOrchestrator

model = OpenAIModel(model="gpt-4")  # Or ClaudeModel, etc.

orchestrator = AgentOrchestrator(model)

result = orchestrator.analyze("AAPL", time_horizon="both")

from pprint import pprint

pprint(result["final_recommendation"])
