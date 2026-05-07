"""Build a Strands Agent bound to one of the three tables.

The agent's system prompt is generated from the table's schema and a small
sample, so we don't hardcode prompts per table.
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from strands import Agent
from strands.models.anthropic import AnthropicModel

from ato_app.agents.tools import describe_table, forecast, run_sql
from ato_app.db import engine

load_dotenv()

DEFAULT_MODEL_ID = os.getenv("STRANDS_MODEL_ID", "claude-sonnet-4-6")


def _api_key() -> str:
    # accept any of the common names so we don't break on .env mismatches
    for name in ("STRANDS_API_KEY", "ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
        v = os.getenv(name)
        if v:
            return v
    raise RuntimeError(
        "No API key found. Set STRANDS_API_KEY, ANTHROPIC_API_KEY, or CLAUDE_API_KEY."
    )


def _get_schema(table_name: str) -> list[dict]:
    insp = inspect(engine)
    return [{"name": c["name"], "type": str(c["type"])} for c in insp.get_columns(table_name)]


def _get_sample(table_name: str, n: int = 5) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {n}")).mappings().all()
    return [dict(r) for r in rows]


@lru_cache(maxsize=1)
def _model() -> AnthropicModel:
    return AnthropicModel(
        client_args={"api_key": _api_key()},
        model_id=DEFAULT_MODEL_ID,
        max_tokens=2048,
        params={"temperature": 0.3},
    )


def build_agent_for_table(table_name: str, extra_persona: str = "") -> Agent:
    """Single-table specialist used by /create-agent → /chat/[id]."""
    schema = _get_schema(table_name)
    sample = _get_sample(table_name, n=5)
    system_prompt = f"""
You are a data analyst agent for the `{table_name}` table.

Schema: {schema}
Sample rows: {sample}

Rules:
- Use run_sql for every data question. Never invent values.
- Only SELECT statements are allowed; the tool will reject anything else.
- If the user asks for a forecast on revenue_timeseries, call the forecast tool
  with model in {{linear, random_forest, arima}}.
- Be concise. Show numbers, not preamble.

{extra_persona}
""".strip()

    return Agent(
        model=_model(),
        system_prompt=system_prompt,
        tools=[run_sql, describe_table, forecast],
        callback_handler=None,
    )


# --------------------------------------------------------------------------
# Orchestrator: home-page chat uses a router agent that delegates to three
# table-specialist agents wrapped as tools.
# --------------------------------------------------------------------------

_SPECIALIST_DESCRIPTIONS = {
    "customers": (
        "Answer questions about customers — tier, industry, region, country, "
        "MRR, seats, signup/churn dates, active vs churned. Use this for "
        "anything about who the customers are, churn rates, or revenue per "
        "customer segment."
    ),
    "revenue_timeseries": (
        "Answer questions about daily revenue, units sold, marketing spend, "
        "active users, holidays, seasonality, or promo days. Use this for "
        "trend questions and to forecast future revenue (linear / "
        "random_forest / arima)."
    ),
}


def _build_specialist(table_name: str):
    """Specialist agent + the descriptive tool wrapper for the orchestrator."""
    agent = build_agent_for_table(table_name)
    return agent.as_tool(
        name=f"{table_name}_specialist",
        description=_SPECIALIST_DESCRIPTIONS[table_name],
    )


def _build_operations_specialist():
    """Specialist that knows about the user's REAL created agents and trained
    ML models (not the synthetic agent_telemetry seed data)."""
    schemas = {
        "agents": _get_schema("agents"),
        "ml_models": _get_schema("ml_models"),
    }
    samples = {
        "agents": _get_sample("agents", n=3),
        "ml_models": _get_sample("ml_models", n=3),
    }
    system_prompt = f"""
You are the operations specialist. You answer questions about the user's
REAL created agents and trained ML models. You have access to two tables:

`agents` — every agent the user has created via the Agent Core page.
  Schema: {schemas['agents']}
  Sample: {samples['agents']}

`ml_models` — every model the user has trained via the ML Studio page.
  Schema: {schemas['ml_models']}
  Sample: {samples['ml_models']}

Rules:
- Use run_sql for every question. SELECT only.
- "What agents are running" / "what agents do I have" → SELECT from `agents`.
  These are real configured agents; treat them as Active.
- "What models have I trained" / "best model" → SELECT from `ml_models`.
- Do NOT use the agent_telemetry table — that is synthetic seed data and not
  representative of the user's real fleet.
- If either table is empty, say so plainly (e.g. "No agents created yet.").
- Be concise: number/answer first, brief context after.
""".strip()

    agent = Agent(
        model=_model(),
        system_prompt=system_prompt,
        tools=[run_sql, describe_table],
        callback_handler=None,
    )
    return agent.as_tool(
        name="operations_specialist",
        description=(
            "Answer questions about the user's REAL created agents (the "
            "`agents` table) and trained ML models (the `ml_models` table) — "
            "names, bound tables, accuracies, when they were created. Use "
            "this for any 'what agents do I have', 'how many models have I "
            "trained', or 'show me my best model' style question. Do NOT use "
            "the agent_telemetry table — that is synthetic demo data."
        ),
    )


def build_orchestrator_agent() -> Agent:
    """Router agent for the home-page chat — delegates to table specialists."""
    specialist_tools = [
        _build_specialist("customers"),
        _build_specialist("revenue_timeseries"),
        _build_operations_specialist(),
    ]

    system_prompt = """
You are the AI Transformation Office orchestrator. You coordinate three
specialist agents:

- customers_specialist          — customer & churn questions (analytical
                                  data about a synthetic customer base)
- revenue_timeseries_specialist — daily revenue trends & forecasts
                                  (analytical timeseries data)
- operations_specialist         — the user's REAL created agents and
                                  trained ML models (operational truth)

Rules:
- "What agents do I have" / "what's running" / "show my agents" / "models I
  trained" → call operations_specialist. These are the real things the user
  created, not synthetic fleet telemetry.
- Customer or churn questions → customers_specialist.
- Revenue, trend, or forecast questions → revenue_timeseries_specialist.
- If a question crosses domains, call multiple specialists and synthesize.
- Never fabricate numbers. If a specialist returns no data, say so plainly
  (e.g. "You have no agents created yet — go to Agent Core to create one.").
- Keep replies concise: lead with the answer, then a one-line context.
- For "what can you do" / "who are you" — briefly describe the specialists
  without calling tools.
""".strip()

    return Agent(
        model=_model(),
        system_prompt=system_prompt,
        tools=specialist_tools,
        callback_handler=None,
    )
