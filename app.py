"""AI Transformation Office — Gradio frontend.

Reuses the Strands agent factory, ML forecasters, and SQLite schema from
the existing `ato_app/` package. Run with `python app.py`.
"""
from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

import gradio as gr
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
from sqlalchemy import text

# Make sure the seed runs before anything else touches the DB.
from ato_app.db import engine, ensure_seeded  # noqa: E402

load_dotenv()
ensure_seeded()

from ato_app.agents.factory import (  # noqa: E402
    build_agent_for_table,
    build_orchestrator_agent,
)
from ato_app.ml.forecasters import quick_train, revenue_recent  # noqa: E402

TABLES = ["customers", "revenue_timeseries", "agent_telemetry"]
MODEL_TYPES = ["AutoML", "RandomForest", "XGBoost"]
SOURCE_TABLES = ["revenue_timeseries", "customers", "agent_telemetry"]
TABLE_TASK_LABELS = {
    "revenue_timeseries": "regression — predicts daily revenue",
    "customers": "classification — predicts active vs churned",
    "agent_telemetry": "classification — predicts task status",
}

CAPABILITY_BY_TABLE = {
    "customers": (
        "Answers questions about your customer base — tier, industry, region, "
        "country, MRR, seats, signup/churn dates."
    ),
    "revenue_timeseries": (
        "Answers questions about daily revenue, units, marketing spend, "
        "active users, holidays, seasonality. Can also forecast forward."
    ),
    "agent_telemetry": (
        "Answers questions about the AI agent fleet — Running/Idle/Failed/"
        "Completed counts, durations, tokens used."
    ),
}


# ---------------------------------------------------------------------------
# Agent caches (orchestrator for home tab, specialists per agent_id)
# ---------------------------------------------------------------------------
_AGENT_CACHE: dict[str, object] = {}


def _orchestrator():
    if "__orch__" not in _AGENT_CACHE:
        _AGENT_CACHE["__orch__"] = build_orchestrator_agent()
    return _AGENT_CACHE["__orch__"]


def _reset_orchestrator():
    _AGENT_CACHE.pop("__orch__", None)


def _specialist(agent_id: str, table_name: str, persona: str = ""):
    key = f"agent::{agent_id}"
    if key not in _AGENT_CACHE:
        _AGENT_CACHE[key] = build_agent_for_table(table_name, persona)
    return _AGENT_CACHE[key]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _scalar(query: str, default=0):
    with engine.connect() as conn:
        row = conn.execute(text(query)).first()
    if row is None or row[0] is None:
        return default
    return row[0]


def _format_currency(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}k"
    return f"${value:,.0f}"


# ---------------------------------------------------------------------------
# Dashboard data
# ---------------------------------------------------------------------------
def kpi_summary() -> str:
    active_agents = int(_scalar("SELECT COUNT(*) FROM agents"))
    models_trained = int(_scalar("SELECT COUNT(*) FROM ml_models"))
    avg_acc = _scalar("SELECT AVG(accuracy) FROM ml_models", default=None)
    avg_acc_str = f"{float(avg_acc):.2f}%" if avg_acc is not None else "—"
    total_customers = int(_scalar(
        "SELECT COUNT(*) FROM customers WHERE is_active=1"
    ))
    total_mrr = float(_scalar(
        "SELECT SUM(mrr_usd) FROM customers WHERE is_active=1", default=0.0
    ) or 0.0)
    churned = int(_scalar(
        "SELECT COUNT(*) FROM customers WHERE churn_date IS NOT NULL"
    ))
    total = int(_scalar("SELECT COUNT(*) FROM customers"))
    churn_rate = f"{(churned / total * 100):.1f}%" if total else "—"

    rev_recent = float(_scalar(
        "SELECT SUM(revenue_usd) FROM (SELECT revenue_usd FROM revenue_timeseries "
        "ORDER BY date DESC LIMIT 30)", default=0.0
    ) or 0.0)

    return (
        "| Metric | Value |\n|---|---|\n"
        f"| Active Agents | **{active_agents}** |\n"
        f"| Models Trained | **{models_trained}** |\n"
        f"| Avg Model Accuracy | **{avg_acc_str}** |\n"
        f"| Active Customers | **{total_customers:,}** |\n"
        f"| Total MRR | **{_format_currency(total_mrr)}** |\n"
        f"| Churn Rate | **{churn_rate}** |\n"
        f"| 30-day Revenue | **{_format_currency(rev_recent)}** |\n"
    )


def revenue_chart_fig() -> go.Figure:
    data = revenue_recent(30)
    df = pd.DataFrame(data)
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["revenue_usd"],
            mode="lines",
            line=dict(color="#3B82F6", width=2),
            fill="tozeroy",
            fillcolor="rgba(59, 130, 246, 0.08)",
            name="Revenue",
        ))
    fig.update_layout(
        title="30-day Revenue",
        height=280,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#E5E7EB", tickprefix="$"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    return fig


def tier_chart_fig() -> go.Figure:
    df = pd.read_sql(
        "SELECT tier, COUNT(*) AS cnt, "
        "SUM(CASE WHEN is_active=1 THEN mrr_usd ELSE 0 END) AS mrr "
        "FROM customers GROUP BY tier",
        engine,
    )
    order = {"Enterprise": 0, "Mid-Market": 1, "SMB": 2}
    df = df.sort_values(by="tier", key=lambda s: s.map(order).fillna(99))
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["tier"], y=df["mrr"],
        marker_color="#3B82F6",
        text=[_format_currency(v) for v in df["mrr"]],
        textposition="outside",
        name="MRR",
    ))
    fig.update_layout(
        title="MRR by Customer Tier",
        height=280,
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
        yaxis=dict(showgrid=True, gridcolor="#E5E7EB", tickprefix="$"),
        showlegend=False,
    )
    return fig


def industries_table() -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT industry, COUNT(*) AS customers, "
        "SUM(CASE WHEN is_active=1 THEN mrr_usd ELSE 0 END) AS mrr "
        "FROM customers GROUP BY industry ORDER BY mrr DESC LIMIT 5",
        engine,
    )
    df["mrr"] = df["mrr"].map(_format_currency)
    df.columns = ["Industry", "Customers", "Active MRR"]
    return df


# ---------------------------------------------------------------------------
# Agent Core data
# ---------------------------------------------------------------------------
def agents_dataframe() -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT name AS Name, table_name AS \"Bound Table\", "
        "COALESCE(description, '') AS Description, "
        "DATE(created_at) AS Created, agent_id AS \"Agent ID\" "
        "FROM agents ORDER BY created_at DESC",
        engine,
    )
    return df


def create_agent(name: str, table_name: str, description: str, persona: str):
    name = (name or "").strip()
    if not name:
        return agents_dataframe(), "**Please enter a name.**", "", "customers", "", ""
    agent_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO agents "
                "(agent_id, name, table_name, description, persona, created_at) "
                "VALUES (:id, :n, :t, :d, :p, :ts)"
            ),
            {
                "id": agent_id,
                "n": name,
                "t": table_name,
                "d": (description or "").strip(),
                "p": (persona or "").strip(),
                "ts": dt.datetime.utcnow(),
            },
        )
    _reset_orchestrator()  # so operations_specialist sees the new row
    msg = f"✓ Created agent **{name}** (ID `{agent_id[:8]}…`). Switch to the Chat with Agent tab to talk to it."
    # Reset the form fields
    return agents_dataframe(), msg, "", "customers", "", ""


def agent_choices() -> list[str]:
    df = pd.read_sql(
        "SELECT name, agent_id FROM agents ORDER BY created_at DESC", engine
    )
    if df.empty:
        return []
    return [f"{r['name']} ({r['agent_id'][:8]})" for _, r in df.iterrows()]


def agent_id_from_choice(choice: str) -> str:
    if not choice:
        return ""
    # encoded as "name (xxxxxxxx)"
    suffix = choice.rsplit("(", 1)[-1].rstrip(")").strip()
    df = pd.read_sql("SELECT agent_id FROM agents", engine)
    for aid in df["agent_id"]:
        if aid.startswith(suffix):
            return aid
    return ""


def agent_detail(agent_id: str) -> str:
    if not agent_id:
        return "*Pick an agent above to load details.*"
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT name, table_name, description, persona, created_at "
                 "FROM agents WHERE agent_id=:id"),
            {"id": agent_id},
        ).first()
    if row is None:
        return "*Agent not found.*"
    name, table_name, description, persona, created_at = row
    cap = CAPABILITY_BY_TABLE.get(table_name, "")
    blocks = [
        f"### {name}",
        f"**Bound Table:** `{table_name}`  ·  **Created:** {str(created_at)[:10]}",
    ]
    if description:
        blocks.append(f"**Description:** {description}")
    blocks.append(f"_{cap}_")
    if persona:
        blocks.append(f"**Persona / extra system prompt:**\n```\n{persona}\n```")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# ML Studio data
# ---------------------------------------------------------------------------
def models_dataframe() -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT name AS Name, model_type AS Type, source_table AS Source, "
        "ROUND(accuracy, 2) AS \"Accuracy %\", "
        "ROUND(mae, 2) AS MAE, "
        "ROUND(training_secs, 2) AS \"Train (s)\", "
        "DATE(created_at) AS Created "
        "FROM ml_models ORDER BY created_at DESC",
        engine,
    )
    return df


def train_model(name: str, source: str, model_type: str):
    name = (name or "").strip()
    if not name:
        return models_dataframe(), "**Please enter a model name.**", "", "revenue_timeseries", "AutoML"
    try:
        result = quick_train(model_type, source)
    except Exception as e:
        return models_dataframe(), f"**Training failed:** {e}", name, source, model_type

    model_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ml_models "
                "(model_id, name, model_type, source_table, task, metric, "
                "accuracy, mae, training_secs, created_at) "
                "VALUES (:id, :n, :mt, :src, :tk, :m, :a, :mae, :s, :ts)"
            ),
            {
                "id": model_id,
                "n": name,
                "mt": result["model_type"],
                "src": result["source_table"],
                "tk": result["task"],
                "m": result["metric"],
                "a": result["accuracy"],
                "mae": result["mae"],
                "s": result["training_secs"],
                "ts": dt.datetime.utcnow(),
            },
        )
    _reset_orchestrator()
    msg = (
        f"✓ Trained **{result['model_type']}** on `{source}` — "
        f"accuracy {result['accuracy']:.2f}% in {result['training_secs']:.2f}s "
        f"({result['n_rows']:,} rows)"
    )
    # Reset form
    return models_dataframe(), msg, "", "revenue_timeseries", "AutoML"


# ---------------------------------------------------------------------------
# Chat handlers
# ---------------------------------------------------------------------------
async def stream_orchestrator(message: str, history: list[dict]):
    if not message.strip():
        yield history, ""
        return
    history = list(history) + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": ""},
    ]
    yield history, ""
    agent = _orchestrator()
    full_text = ""
    pending = ""  # buffer so we yield once per ~40 chars instead of per token
    try:
        async for event in agent.stream_async(message):
            chunk = event.get("data", "") if isinstance(event, dict) else ""
            if not chunk:
                continue
            full_text += chunk
            pending += chunk
            if len(pending) >= 40 or "\n" in pending:
                history[-1]["content"] = full_text
                yield history, ""
                pending = ""
    except Exception as e:
        full_text = _format_error(e)
        history[-1]["content"] = full_text
        yield history, ""
        return
    if not full_text:
        try:
            full_text = str(agent(message))
        except Exception as e:
            full_text = _format_error(e)
    history[-1]["content"] = full_text
    yield history, ""


async def stream_specialist(message: str, history: list[dict], agent_choice: str):
    agent_id = agent_id_from_choice(agent_choice)
    if not agent_id:
        history = list(history) + [
            {"role": "user", "content": message},
            {"role": "assistant",
             "content": "_Pick an agent from the dropdown above first._"},
        ]
        yield history, ""
        return
    if not message.strip():
        yield history, ""
        return
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT table_name, persona FROM agents WHERE agent_id=:id"),
            {"id": agent_id},
        ).first()
    if row is None:
        yield history, ""
        return
    table_name, persona = row
    agent = _specialist(agent_id, table_name, persona or "")

    history = list(history) + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": ""},
    ]
    yield history, ""

    full_text = ""
    pending = ""
    try:
        async for event in agent.stream_async(message):
            chunk = event.get("data", "") if isinstance(event, dict) else ""
            if not chunk:
                continue
            full_text += chunk
            pending += chunk
            if len(pending) >= 40 or "\n" in pending:
                history[-1]["content"] = full_text
                yield history, ""
                pending = ""
    except Exception as e:
        full_text = _format_error(e)
        history[-1]["content"] = full_text
        yield history, ""
        return
    if not full_text:
        try:
            full_text = str(agent(message))
        except Exception as e:
            full_text = _format_error(e)
    history[-1]["content"] = full_text
    yield history, ""


def _format_error(err: Exception) -> str:
    text_ = str(err)
    if "credit balance is too low" in text_.lower():
        return (
            "⚠️ **Anthropic API rejected the request:** your account has no "
            "credit. Top up at https://console.anthropic.com/settings/billing."
        )
    if "invalid x-api-key" in text_.lower() or "invalid api key" in text_.lower():
        return "⚠️ The API key in `.env` is not valid."
    return f"⚠️ {type(err).__name__}: {text_}"


def on_agent_picked(choice: str):
    """Single combined handler for the agent dropdown change event:
    refresh the detail markdown AND clear the conversation thread."""
    return agent_detail(agent_id_from_choice(choice)), []


def refresh_agent_picker():
    """Return a fresh Dropdown component (Gradio 6 idiom for updates)."""
    choices = agent_choices()
    return gr.Dropdown(choices=choices, value=None)


# ---------------------------------------------------------------------------
# Build the Gradio app
# ---------------------------------------------------------------------------
HEADER_HTML = """
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:12px 16px;background:white;border-bottom:1px solid #E5E7EB;
            border-radius:12px;margin-bottom:8px">
  <div>
    <div style="font-size:20px;font-weight:700;color:#0F172A">
      AI Transformation Office
    </div>
    <div style="font-size:13px;color:#64748B">
      Strands orchestrator · scikit-learn / XGBoost ML Studio · SQLite
    </div>
  </div>
  <div style="font-size:13px;color:#64748B">FY 2025–2026 · GF</div>
</div>
"""


with gr.Blocks(title="AI Transformation Office") as demo:
    gr.HTML(HEADER_HTML)

    with gr.Tabs():
        # ===================== DASHBOARD =====================
        with gr.Tab("Dashboard"):
            with gr.Row():
                with gr.Column(scale=5):
                    gr.Markdown("### Orchestrator Chat")
                    gr.Markdown(
                        "_Routes questions across customers, revenue, "
                        "and operations specialists._"
                    )
                    home_chat = gr.Chatbot(height=440)
                    home_msg = gr.Textbox(
                        placeholder='Try: "How many enterprise finance customers churned?"',
                        show_label=False,
                    )
                    with gr.Row():
                        home_send = gr.Button("Send", variant="primary", scale=1)
                        home_clear = gr.Button("Clear", scale=0)

                with gr.Column(scale=4):
                    gr.Markdown("### KPIs")
                    kpi_md = gr.Markdown(kpi_summary, elem_classes="kpi-table")
                    refresh_btn = gr.Button("Refresh", size="sm")
                    revenue_plot = gr.Plot(value=revenue_chart_fig(),
                                           show_label=False)
                    tier_plot = gr.Plot(value=tier_chart_fig(),
                                        show_label=False)
                    gr.Markdown("**Top Industries (by active MRR)**")
                    industries_df = gr.Dataframe(
                        value=industries_table(),
                        interactive=False, wrap=True,
                    )

            home_msg.submit(
                stream_orchestrator,
                [home_msg, home_chat], [home_chat, home_msg],
                concurrency_limit=8, queue=True,
            )
            home_send.click(
                stream_orchestrator,
                [home_msg, home_chat], [home_chat, home_msg],
                concurrency_limit=8, queue=True,
            )
            home_clear.click(lambda: [], outputs=home_chat)
            refresh_btn.click(
                lambda: (kpi_summary(), revenue_chart_fig(),
                         tier_chart_fig(), industries_table()),
                outputs=[kpi_md, revenue_plot, tier_plot, industries_df],
            )

        # ===================== AGENT CORE =====================
        with gr.Tab("Agent Core"):
            gr.Markdown("### Created Agents")
            agents_table_view = gr.Dataframe(
                value=agents_dataframe(),
                interactive=False,
            )

            with gr.Accordion("+ New Agent", open=True):
                a_name = gr.Textbox(label="Agent name",
                                    placeholder="e.g. Customer Insights Agent")
                a_table = gr.Dropdown(TABLES, value="customers",
                                      label="Bound table")
                a_desc = gr.Textbox(
                    label="Description",
                    lines=2,
                    placeholder='e.g. "Answers churn-related questions for the sales team."',
                )
                a_persona = gr.Textbox(
                    label="Persona / extra system prompt",
                    lines=4,
                    placeholder='Optional. e.g. "Focus on enterprise tier."',
                )
                a_create = gr.Button("Create Agent", variant="primary")
                a_status = gr.Markdown()

            a_create.click(
                create_agent,
                [a_name, a_table, a_desc, a_persona],
                [agents_table_view, a_status, a_name, a_table, a_desc, a_persona],
            )

        # ===================== CHAT WITH AGENT =====================
        with gr.Tab("Chat with Agent"):
            gr.Markdown("### Talk to a created agent")
            _initial_choices = agent_choices()
            agent_picker = gr.Dropdown(
                choices=_initial_choices,
                value=None,
                label="Select an agent",
                interactive=True,
            )
            agent_picker_refresh = gr.Button("Refresh list", size="sm")
            agent_detail_md = gr.Markdown(
                "*Pick an agent above to load details.*"
            )
            specialist_chat = gr.Chatbot(height=400)
            specialist_msg = gr.Textbox(
                placeholder="Ask a question...", show_label=False,
            )
            with gr.Row():
                specialist_send = gr.Button("Send", variant="primary", scale=1)
                specialist_clear = gr.Button("Clear thread", scale=0)

            agent_picker_refresh.click(
                refresh_agent_picker,
                outputs=agent_picker,
            )
            agent_picker.change(
                on_agent_picked,
                inputs=agent_picker,
                outputs=[agent_detail_md, specialist_chat],
            )

            specialist_msg.submit(
                stream_specialist,
                [specialist_msg, specialist_chat, agent_picker],
                [specialist_chat, specialist_msg],
                concurrency_limit=8, queue=True,
            )
            specialist_send.click(
                stream_specialist,
                [specialist_msg, specialist_chat, agent_picker],
                [specialist_chat, specialist_msg],
                concurrency_limit=8, queue=True,
            )
            specialist_clear.click(lambda: [], outputs=specialist_chat)

        # ===================== ML STUDIO =====================
        with gr.Tab("ML Studio"):
            gr.Markdown("### Trained Models")
            models_table_view = gr.Dataframe(
                value=models_dataframe(), interactive=False,
            )

            with gr.Accordion("+ New Model", open=True):
                m_name = gr.Textbox(label="Model name",
                                    placeholder="e.g. Revenue Forecaster v1")
                m_source = gr.Dropdown(SOURCE_TABLES,
                                       value="revenue_timeseries",
                                       label="Source table")
                m_task_md = gr.Markdown(
                    f"_{TABLE_TASK_LABELS['revenue_timeseries']}_"
                )
                m_source.change(
                    lambda t: f"_{TABLE_TASK_LABELS.get(t, '')}_",
                    inputs=m_source, outputs=m_task_md,
                )
                m_type = gr.Dropdown(MODEL_TYPES, value="AutoML",
                                     label="Model type")
                gr.Markdown(
                    "_AutoML trains both RandomForest and XGBoost and keeps the better one._"
                )
                m_train_btn = gr.Button("Train", variant="primary")
                m_status = gr.Markdown()

            m_train_btn.click(
                train_model,
                [m_name, m_source, m_type],
                [models_table_view, m_status, m_name, m_source, m_type],
            )


if __name__ == "__main__":
    import os
    share = os.getenv("GRADIO_SHARE", "").lower() in ("1", "true", "yes")
    # `default_concurrency_limit` raises the per-event ceiling so multiple
    # users can interact at once without queueing behind each other.
    demo.queue(default_concurrency_limit=8, max_size=64)
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", 7860)),
        share=share,
        theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
        css=".gradio-container { max-width: 1280px !important; }",
    )
