"""Build and seed the synthetic SQLite database at data/app.db.

Three tables:
    customers          ~1,000 rows  — Q&A workload
    revenue_timeseries ~3 years     — forecasting workload
    agent_telemetry    ~5,000 rows  — agent-task log

Plus a small `agents` table for user-created agents (from /create-agent).

Run directly with `python data/seed.py`, or call `seed.main()`.
"""
from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "app.db"
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

SEED = 42
N_CUSTOMERS = 1_000
N_TELEMETRY = 5_000
HISTORY_YEARS = 3

INDUSTRIES = [
    "Finance", "Healthcare", "Retail", "Manufacturing", "Technology",
    "Energy", "Education", "Media", "Logistics", "Insurance",
]
REGIONS = ["NA", "EMEA", "APAC", "LATAM"]
TIERS = ["SMB", "Mid-Market", "Enterprise"]

AGENT_NAMES = [
    "Document Processor Agent", "Data Pipeline Agent", "Alert Monitor Agent",
    "Report Generator Agent", "Customer Insights Agent", "Forecast Agent",
    "QA Triage Agent", "Compliance Auditor Agent",
]
AGENT_TYPES = ["LLM", "Workflow", "Retriever", "Classifier"]
TELEMETRY_STATUSES = ["Running", "Idle", "Failed", "Completed"]
TELEMETRY_STATUS_WEIGHTS = [0.45, 0.20, 0.05, 0.30]

INPUT_SAMPLES = [
    "Summarize Q3 churn for enterprise tier",
    "Score document /docs/contract_482.pdf",
    "Forecast next 30 days revenue",
    "Triage failed pipeline run #1281",
    "Generate weekly executive report",
    "Classify support ticket batch",
    "Reconcile invoice mismatches",
    "Detect anomalies in latency metrics",
]
OUTPUT_SAMPLES = [
    "Completed — 12 rows updated",
    "OK — confidence 0.94",
    "Forecast generated, MAE 4.2%",
    "Routed to on-call",
    "Report delivered to #exec-readouts",
    "112 tickets classified",
    "3 mismatches flagged",
    "No anomalies detected",
]

metadata = MetaData()

customers = Table(
    "customers", metadata,
    Column("customer_id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("industry", String, nullable=False),
    Column("region", String, nullable=False),
    Column("country", String, nullable=False),
    Column("tier", String, nullable=False),
    Column("signup_date", Date, nullable=False),
    Column("churn_date", Date, nullable=True),
    Column("mrr_usd", Float, nullable=False),
    Column("seats", Integer, nullable=False),
    Column("is_active", Boolean, nullable=False),
)

revenue_timeseries = Table(
    "revenue_timeseries", metadata,
    Column("date", Date, primary_key=True),
    Column("revenue_usd", Float, nullable=False),
    Column("units_sold", Integer, nullable=False),
    Column("marketing_spend", Float, nullable=False),
    Column("active_users", Integer, nullable=False),
    Column("is_holiday", Boolean, nullable=False),
    Column("season", String, nullable=False),
    Column("promo_active", Boolean, nullable=False),
)

agent_telemetry = Table(
    "agent_telemetry", metadata,
    Column("task_id", String, primary_key=True),
    Column("agent_name", String, nullable=False),
    Column("agent_type", String, nullable=False),
    Column("status", String, nullable=False),
    Column("started_at", DateTime, nullable=False),
    Column("duration_ms", Integer, nullable=False),
    Column("tokens_used", Integer, nullable=False),
    Column("input_summary", String, nullable=False),
    Column("output_summary", String, nullable=False),
)

# 4th table: persisted user-created agents (from /create-agent)
agents = Table(
    "agents", metadata,
    Column("agent_id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("table_name", String, nullable=False),
    Column("description", String, nullable=True),
    Column("persona", String, nullable=True),
    Column("created_at", DateTime, nullable=False),
)

# 5th table: persisted user-trained ML models (from /ml-studio)
ml_models = Table(
    "ml_models", metadata,
    Column("model_id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("model_type", String, nullable=False),     # RandomForest, XGBoost, AutoML
    Column("source_table", String, nullable=False),   # which DB table it trained on
    Column("task", String, nullable=False),           # classification or regression
    Column("metric", String, nullable=False),         # "accuracy" or "mae"
    Column("accuracy", Float, nullable=False),        # display metric (0-100)
    Column("mae", Float, nullable=False),
    Column("training_secs", Float, nullable=False),
    Column("created_at", DateTime, nullable=False),
)


def _season_for(d: date) -> str:
    m = d.month
    if m in (12, 1, 2):
        return "Winter"
    if m in (3, 4, 5):
        return "Spring"
    if m in (6, 7, 8):
        return "Summer"
    return "Fall"


def _build_customers(fake: Faker, rng: random.Random) -> list[dict]:
    rows: list[dict] = []
    today = date.today()
    for _ in range(N_CUSTOMERS):
        signup = fake.date_between(start_date="-4y", end_date="-30d")
        tier = rng.choices(TIERS, weights=[0.55, 0.30, 0.15])[0]
        if tier == "Enterprise":
            mrr = rng.uniform(8_000, 45_000)
            seats = rng.randint(50, 1500)
        elif tier == "Mid-Market":
            mrr = rng.uniform(1_500, 9_000)
            seats = rng.randint(15, 200)
        else:
            mrr = rng.uniform(150, 2_000)
            seats = rng.randint(1, 25)

        churned = rng.random() < 0.18
        churn_dt = (
            fake.date_between(start_date=signup, end_date=today) if churned else None
        )
        rows.append(dict(
            customer_id=str(uuid.UUID(int=rng.getrandbits(128))),
            name=fake.company(),
            industry=rng.choice(INDUSTRIES),
            region=rng.choice(REGIONS),
            country=fake.country(),
            tier=tier,
            signup_date=signup,
            churn_date=churn_dt,
            mrr_usd=round(mrr, 2),
            seats=seats,
            is_active=churn_dt is None,
        ))
    return rows


def _build_revenue(rng: np.random.Generator) -> list[dict]:
    end = date.today()
    start = end - timedelta(days=HISTORY_YEARS * 365)
    days = (end - start).days + 1
    dates = [start + timedelta(days=i) for i in range(days)]
    t = np.arange(days)

    trend = 12_000 + 4.5 * t  # gentle linear growth
    weekly = 1_800 * np.sin(2 * np.pi * t / 7)  # weekly seasonality
    yearly = 5_500 * np.sin(2 * np.pi * t / 365)  # yearly seasonality
    noise = rng.normal(0, 900, size=days)

    revenue = trend + weekly + yearly + noise
    revenue = np.maximum(revenue, 1_000)

    rows: list[dict] = []
    for i, d in enumerate(dates):
        is_holiday = (d.month, d.day) in {
            (1, 1), (7, 4), (11, 28), (12, 25), (12, 31),
        }
        promo = bool(rng.random() < 0.07)
        bump = (1.18 if is_holiday else 1.0) * (1.10 if promo else 1.0)
        rev = float(revenue[i] * bump)
        units = int(rev / rng.uniform(45, 65))
        spend = float(rev * rng.uniform(0.08, 0.18))
        users = int(rng.uniform(8_000, 22_000) + 30 * t[i])
        rows.append(dict(
            date=d,
            revenue_usd=round(rev, 2),
            units_sold=units,
            marketing_spend=round(spend, 2),
            active_users=users,
            is_holiday=is_holiday,
            season=_season_for(d),
            promo_active=promo,
        ))
    return rows


def _build_telemetry(rng: random.Random) -> list[dict]:
    rows: list[dict] = []
    now = datetime.utcnow()
    for _ in range(N_TELEMETRY):
        started = now - timedelta(minutes=rng.randint(0, 60 * 24 * 30))
        status = rng.choices(TELEMETRY_STATUSES, weights=TELEMETRY_STATUS_WEIGHTS)[0]
        rows.append(dict(
            task_id=str(uuid.UUID(int=rng.getrandbits(128))),
            agent_name=rng.choice(AGENT_NAMES),
            agent_type=rng.choice(AGENT_TYPES),
            status=status,
            started_at=started,
            duration_ms=rng.randint(120, 28_000),
            tokens_used=rng.randint(80, 12_000),
            input_summary=rng.choice(INPUT_SAMPLES),
            output_summary=rng.choice(OUTPUT_SAMPLES),
        ))
    return rows


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(DB_URL, future=True)
    metadata.drop_all(engine)
    metadata.create_all(engine)

    Faker.seed(SEED)
    py_rng = random.Random(SEED)
    np_rng = np.random.default_rng(SEED)
    fake = Faker()

    cust_rows = _build_customers(fake, py_rng)
    rev_rows = _build_revenue(np_rng)
    tel_rows = _build_telemetry(py_rng)

    with engine.begin() as conn:
        conn.execute(customers.insert(), cust_rows)
        # bulk insert in chunks for revenue (~1100 rows is fine in one)
        conn.execute(revenue_timeseries.insert(), rev_rows)
        # telemetry: chunk to keep it snappy
        for i in range(0, len(tel_rows), 1000):
            conn.execute(agent_telemetry.insert(), tel_rows[i : i + 1000])

    print(
        f"Seeded {len(cust_rows)} customers, "
        f"{len(rev_rows)} revenue rows, "
        f"{len(tel_rows)} telemetry rows -> {DB_PATH}"
    )


if __name__ == "__main__":
    main()
