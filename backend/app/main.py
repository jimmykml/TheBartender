import logging
import traceback
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_ai import Agent

from agents.news_agent import NewsAgent
from agents.fiscal_agent import FiscalAgent
from app.config import get_settings
from clients.llm import build_model
from core.usage_tracker import compute_cost

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="The Bartender API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewsRequest(BaseModel):
    ticker: str
    from_date: date
    to_date: date


class FiscalRequest(BaseModel):
    ticker: str


class FiscalAskRequest(BaseModel):
    question: str
    report_context: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/news")
async def analyze_news(req: NewsRequest) -> dict:
    try:
        agent = NewsAgent()
        result = await agent.run_from_inputs(
            ticker=req.ticker.upper(),
            from_date=str(req.from_date),
            to_date=str(req.to_date),
        )
        usage = agent.compute_usage()
        return {"data": result.model_dump(), "usage": usage.model_dump() if usage else None}
    except Exception as e:
        logger.error("analyze_news failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/fiscal")
async def analyze_fiscal(req: FiscalRequest) -> dict:
    try:
        agent = FiscalAgent()
        result = await agent.run_from_inputs(ticker=req.ticker.upper())
        usage = agent.compute_usage()
        return {"data": result.model_dump(), "usage": usage.model_dump() if usage else None}
    except Exception as e:
        logger.error("analyze_fiscal failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/fiscal/ask")
async def ask_fiscal(req: FiscalAskRequest) -> dict:
    try:
        settings = get_settings()
        model_name = settings.default_model
        agent: Agent[None, str] = Agent(
            build_model(),
            system_prompt=(
                "You are a financial analyst. Answer questions concisely and precisely "
                "based only on the financial report provided. Cite specific numbers.\n\n"
                f"--- FINANCIAL REPORT ---\n{req.report_context}"
            ),
        )
        result = await agent.run(req.question)
        usage = compute_cost(model_name, result.usage())
        return {"answer": result.output, "usage": usage.model_dump()}
    except Exception as e:
        logger.error("ask_fiscal failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
