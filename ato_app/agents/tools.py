"""Strands tools the agent can call.

- ``run_sql``        — read-only SELECT against data/app.db
- ``describe_table`` — schema + sample rows
- ``forecast``       — fit a model on revenue_timeseries and return predictions
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from sqlalchemy import inspect, text
from strands import tool

from ato_app.db import engine

ALLOWED_TABLES = {
    "customers", "revenue_timeseries", "agent_telemetry",
    "agents", "ml_models",
}
_SELECT_RE = re.compile(r"^\s*(select|with|pragma|explain)\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|replace|truncate)\b",
    re.IGNORECASE,
)


def _serialize(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


@tool
def run_sql(query: str) -> list[dict]:
    """Execute a read-only SQL query against the application database.

    Only SELECT (or WITH/PRAGMA/EXPLAIN) statements are accepted. Any DDL or
    write statement is rejected. Returns a list of row dicts (max 500 rows).

    Args:
        query: A single SQL SELECT statement.

    Returns:
        A list of dictionaries, one per row.
    """
    if not query or ";" in query.strip().rstrip(";"):
        return [{"error": "Only a single statement is allowed."}]
    if not _SELECT_RE.match(query):
        return [{"error": "Only SELECT/WITH/PRAGMA/EXPLAIN statements are allowed."}]
    if _FORBIDDEN_RE.search(query):
        return [{"error": "Write statements are not permitted."}]

    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = result.mappings().all()
    out: list[dict] = []
    for r in rows[:500]:
        out.append({k: _serialize(v) for k, v in r.items()})
    return out


@tool
def describe_table(name: str) -> dict:
    """Return the schema and a small sample of rows for a table.

    Args:
        name: One of customers, revenue_timeseries, agent_telemetry, agents.

    Returns:
        Dict with keys ``columns`` (list of {name, type}) and ``sample_rows``.
    """
    if name not in ALLOWED_TABLES:
        return {"error": f"Unknown table: {name}"}
    insp = inspect(engine)
    cols = [{"name": c["name"], "type": str(c["type"])} for c in insp.get_columns(name)]
    with engine.connect() as conn:
        sample = conn.execute(text(f"SELECT * FROM {name} LIMIT 5")).mappings().all()
    return {
        "columns": cols,
        "sample_rows": [{k: _serialize(v) for k, v in r.items()} for r in sample],
    }


@tool
def forecast(model: str, horizon_days: int = 30) -> dict:
    """Forecast daily revenue from the revenue_timeseries table.

    Args:
        model: One of ``linear``, ``random_forest``, ``arima``.
        horizon_days: Number of days to forecast (1-180).

    Returns:
        Dict with ``dates``, ``predictions``, and in-sample ``mae``.
    """
    horizon_days = max(1, min(180, int(horizon_days)))
    from ato_app.ml.forecasters import run_forecast
    return run_forecast(model, horizon_days)
