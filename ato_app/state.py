"""Global Reflex state — one State for the whole app.

Reflex doesn't allow non-serializable values in state, so the live ``Agent``
instances are kept in a module-level cache keyed by table+persona.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import pandas as pd
import reflex as rx
from sqlalchemy import text

from ato_app.db import engine, ensure_seeded


# ---- Module-level agent cache (Agents are not JSON serializable) ----------

_AGENT_CACHE: dict[str, Any] = {}
_ORCHESTRATOR_KEY = "__orchestrator__"


def _agent_for(table_name: str, persona: str = ""):
    """Single-table specialist (used by /chat/[id])."""
    from ato_app.agents.factory import build_agent_for_table  # lazy import
    key = f"{table_name}::{persona}"
    if key not in _AGENT_CACHE:
        _AGENT_CACHE[key] = build_agent_for_table(table_name, persona)
    return _AGENT_CACHE[key]


def _orchestrator():
    """Router agent (used by the home-page chat)."""
    from ato_app.agents.factory import build_orchestrator_agent  # lazy import
    if _ORCHESTRATOR_KEY not in _AGENT_CACHE:
        _AGENT_CACHE[_ORCHESTRATOR_KEY] = build_orchestrator_agent()
    return _AGENT_CACHE[_ORCHESTRATOR_KEY]


def _reset_agent(table_name: str, persona: str = "") -> None:
    key = f"{table_name}::{persona}"
    _AGENT_CACHE.pop(key, None)


def _reset_orchestrator() -> None:
    _AGENT_CACHE.pop(_ORCHESTRATOR_KEY, None)


# ---- Helpers --------------------------------------------------------------

def _scalar(query: str, default: Any = 0) -> Any:
    with engine.connect() as conn:
        row = conn.execute(text(query)).first()
    if row is None:
        return default
    return row[0] if row[0] is not None else default


def _rows(query: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(query)).mappings().all()
    out = []
    for r in rows:
        d = {}
        for k, v in r.items():
            if isinstance(v, (dt.date, dt.datetime)):
                d[k] = v.isoformat()
            else:
                d[k] = v
        out.append(d)
    return out


# ---- Initial seed-on-startup ---------------------------------------------

ensure_seeded()


# ---- State ----------------------------------------------------------------

TABLES = ["customers", "revenue_timeseries", "agent_telemetry"]

# Plain-English capability blurb shown on the agent detail page.
_CAPABILITY_BY_TABLE = {
    "customers": (
        "Answers questions about your customer base — tier, industry, region, "
        "country, MRR, seats, signup/churn dates. Good for churn analysis, "
        "tier breakdowns, and revenue per segment."
    ),
    "revenue_timeseries": (
        "Answers questions about daily revenue, units sold, marketing spend, "
        "active users, holidays, seasonality, and promo days. Can also "
        "forecast forward using linear / random_forest / arima models."
    ),
    "agent_telemetry": (
        "Answers questions about the AI agent fleet — which agents are "
        "Running / Idle / Failed / Completed, task counts, durations, "
        "and tokens used. Good for fleet health and throughput questions."
    ),
}


class State(rx.State):
    # --- Chat: separate threads for the home orchestrator vs each specialist ---
    # Home page (orchestrator) — shared across the whole session.
    home_messages: list[dict[str, str]] = []
    home_chat_input: str = ""
    home_chat_busy: bool = False
    # /chat/[agent_id] (specialist) — reset when a different agent is loaded.
    specialist_messages: list[dict[str, str]] = []
    specialist_chat_input: str = ""
    specialist_chat_busy: bool = False
    # Which table the active specialist agent is bound to.
    bound_table: str = "customers"

    # --- Dashboard top metrics (real ops + analytical headlines) ---
    active_agents: int = 0
    models_trained: int = 0
    avg_accuracy: str = "—"
    total_customers: int = 0
    total_mrr: str = "$0"
    churn_rate: str = "—"
    revenue_30d: str = "$0"
    revenue_30d_delta: str = ""

    # --- Customer Mix: rows of {tier, count, mrr_total, count_pct, mrr_pct} ---
    tier_breakdown: list[dict] = []

    # --- Top Industries: rows of {industry, count, mrr_total} ---
    top_industries: list[dict] = []

    # --- Recent created agents + recent trained models (last 5 each) ---
    recent_agents: list[dict] = []
    recent_models: list[dict] = []

    # --- 30-day revenue chart (real timeseries) ---
    revenue_chart: list[dict] = []

    # --- Agent Core page (real created agents only, no synthetic telemetry) ---
    agent_core_active: int = 0
    agent_core_tables_bound: int = 0
    agent_core_latest: str = "—"
    agent_core_rows: list[dict] = []

    # --- ML Studio page (real models only, persisted to ml_models table) ---
    ml_models: list[dict] = []
    ml_total: int = 0
    ml_experiments_run: int = 0
    ml_avg_accuracy: str = "—"
    ml_busy_model: str = ""

    # New-model dialog
    ml_dialog_open: bool = False
    ml_new_name: str = ""
    ml_new_type: str = "AutoML"
    ml_new_table: str = "revenue_timeseries"
    ml_train_status: str = ""

    # --- Create Agent dialog (lives on /agent-core) ---
    agent_dialog_open: bool = False
    new_agent_name: str = ""
    new_agent_table: str = "customers"
    new_agent_description: str = ""
    new_agent_persona: str = ""

    # --- /chat/[agent_id] dynamic page ---
    chat_agent_id: str = ""
    chat_agent_name: str = ""
    chat_agent_description: str = ""
    chat_agent_persona: str = ""
    chat_agent_created: str = ""
    chat_agent_capability: str = ""

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    @rx.event
    def load_dashboard(self):
        # Drop the cached orchestrator so the operations specialist's system
        # prompt picks up any newly-created agents/models on this page load.
        _reset_orchestrator()

        # ---- Operational metrics (real user-created entities) ----
        self.active_agents = int(_scalar("SELECT COUNT(*) FROM agents"))
        self.models_trained = int(_scalar("SELECT COUNT(*) FROM ml_models"))
        avg_acc = _scalar("SELECT AVG(accuracy) FROM ml_models", default=None)
        self.avg_accuracy = (
            f"{float(avg_acc):.2f}%" if avg_acc is not None else "—"
        )

        # ---- Customer analytics (from `customers`) ----
        self.total_customers = int(_scalar(
            "SELECT COUNT(*) FROM customers WHERE is_active=1"
        ))
        total_mrr = _scalar(
            "SELECT SUM(mrr_usd) FROM customers WHERE is_active=1",
            default=0.0,
        )
        self.total_mrr = self._format_currency(float(total_mrr or 0.0))

        churned = int(_scalar(
            "SELECT COUNT(*) FROM customers WHERE churn_date IS NOT NULL"
        ))
        total = int(_scalar("SELECT COUNT(*) FROM customers"))
        self.churn_rate = f"{(churned / total * 100):.1f}%" if total else "—"

        # ---- Revenue analytics (from `revenue_timeseries`) ----
        # Last 30 days vs prior 30 days
        rev_recent = float(_scalar(
            "SELECT SUM(revenue_usd) FROM ("
            "SELECT revenue_usd FROM revenue_timeseries "
            "ORDER BY date DESC LIMIT 30)",
            default=0.0,
        ) or 0.0)
        rev_prior = float(_scalar(
            "SELECT SUM(revenue_usd) FROM ("
            "SELECT revenue_usd FROM revenue_timeseries "
            "ORDER BY date DESC LIMIT 30 OFFSET 30)",
            default=0.0,
        ) or 0.0)
        self.revenue_30d = self._format_currency(rev_recent)
        if rev_prior > 0:
            delta_pct = (rev_recent - rev_prior) / rev_prior * 100
            sign = "▲" if delta_pct >= 0 else "▼"
            self.revenue_30d_delta = f"{sign} {abs(delta_pct):.1f}% vs prior 30d"
        else:
            self.revenue_30d_delta = ""

        # ---- Customer Mix: count + MRR per tier ----
        tier_rows = _rows(
            "SELECT tier, COUNT(*) AS cnt, "
            "SUM(CASE WHEN is_active=1 THEN mrr_usd ELSE 0 END) AS mrr "
            "FROM customers GROUP BY tier"
        )
        tier_total_count = sum(int(r["cnt"]) for r in tier_rows) or 1
        tier_total_mrr = sum(float(r["mrr"] or 0) for r in tier_rows) or 1.0
        tier_order = {"Enterprise": 0, "Mid-Market": 1, "SMB": 2}
        tier_rows = sorted(tier_rows, key=lambda r: tier_order.get(r["tier"], 99))
        self.tier_breakdown = [
            {
                "tier": r["tier"],
                "count": int(r["cnt"]),
                "mrr_total": self._format_currency(float(r["mrr"] or 0)),
                "count_pct": round(int(r["cnt"]) / tier_total_count * 100, 1),
                "mrr_pct": round(float(r["mrr"] or 0) / tier_total_mrr * 100, 1),
            }
            for r in tier_rows
        ]

        # ---- Top 5 Industries by active MRR ----
        ind_rows = _rows(
            "SELECT industry, COUNT(*) AS cnt, "
            "SUM(CASE WHEN is_active=1 THEN mrr_usd ELSE 0 END) AS mrr "
            "FROM customers GROUP BY industry "
            "ORDER BY mrr DESC LIMIT 5"
        )
        self.top_industries = [
            {
                "industry": r["industry"],
                "count": int(r["cnt"]),
                "mrr_total": self._format_currency(float(r["mrr"] or 0)),
            }
            for r in ind_rows
        ]

        # Recent agents (last 5 created)
        agent_rows = _rows(
            "SELECT name, table_name, persona, created_at "
            "FROM agents ORDER BY created_at DESC LIMIT 5"
        )
        self.recent_agents = [
            {
                "name": r["name"],
                "table_name": r["table_name"],
                "created": str(r["created_at"])[:10],
            }
            for r in agent_rows
        ]

        # Recent models (last 5 trained)
        rows = _rows(
            "SELECT name, model_type, source_table, accuracy, training_secs, "
            "created_at FROM ml_models ORDER BY created_at DESC LIMIT 5"
        )
        self.recent_models = [
            {
                "name": r["name"],
                "model_type": r["model_type"],
                "source_table": r.get("source_table") or "—",
                "accuracy": f"{float(r['accuracy']):.2f}%",
                "training_secs": f"{float(r['training_secs']):.2f}s",
                "created": str(r["created_at"])[:10],
            }
            for r in rows
        ]

        # 30-day revenue chart (real timeseries — analytical context)
        from ato_app.ml.forecasters import revenue_recent
        self.revenue_chart = revenue_recent(30)

    @rx.event
    def load_agent_core(self):
        # Real created agents only — no synthetic telemetry data.
        self.agent_core_active = int(_scalar("SELECT COUNT(*) FROM agents"))
        self.agent_core_tables_bound = int(_scalar(
            "SELECT COUNT(DISTINCT table_name) FROM agents"
        ))
        latest = _rows(
            "SELECT created_at FROM agents ORDER BY created_at DESC LIMIT 1"
        )
        self.agent_core_latest = (
            latest[0]["created_at"][:10] if latest else "—"
        )
        rows = _rows(
            "SELECT agent_id, name, table_name, persona, created_at "
            "FROM agents ORDER BY created_at DESC"
        )
        out: list[dict] = []
        for r in rows:
            out.append({
                "agent_id": r["agent_id"],
                "agent_name": r["name"],
                "status": "Active",
                "bound_table": r["table_name"],
                "created": str(r["created_at"])[:10],
                "detail_href": f"/chat/{r['agent_id']}",
            })
        self.agent_core_rows = out

    def _load_ml_models_from_db(self) -> None:
        rows = _rows(
            "SELECT model_id, name, model_type, source_table, task, metric, "
            "accuracy, mae, training_secs, created_at "
            "FROM ml_models ORDER BY created_at DESC"
        )
        out: list[dict] = []
        for r in rows:
            task = r.get("task") or "regression"
            out.append({
                "model_id": r["model_id"],
                "name": r["name"],
                "model_type": r["model_type"],
                "source_table": r.get("source_table") or "—",
                "task": task,
                "accuracy": f"{float(r['accuracy']):.2f}%",
                "accuracy_num": float(r["accuracy"]),
                "mae": (
                    f"{float(r['mae']):.2f}" if task == "regression" else "—"
                ),
                "training_secs": f"{float(r['training_secs']):.2f}s",
                "created": str(r["created_at"])[:10],
            })
        self.ml_models = out

    @rx.event
    def load_ml_studio(self):
        self._load_ml_models_from_db()
        self.ml_total = len(self.ml_models)
        self.ml_experiments_run = self.ml_total  # 1 experiment per trained model
        if self.ml_models:
            avg = sum(m["accuracy_num"] for m in self.ml_models) / len(self.ml_models)
            self.ml_avg_accuracy = f"{avg:.2f}%"
        else:
            self.ml_avg_accuracy = "—"

    # ------------------------------------------------------------------
    # ML retrain
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # ML Studio — new-model dialog & training
    # ------------------------------------------------------------------

    @rx.event
    def open_new_model_dialog(self):
        # Reset form fields ONCE on open (not on every state sync).
        self.ml_new_name = ""
        self.ml_new_type = "AutoML"
        self.ml_new_table = "revenue_timeseries"
        self.ml_train_status = ""
        self.ml_dialog_open = True

    @rx.event
    def close_new_model_dialog(self):
        self.ml_dialog_open = False

    @rx.event
    def set_ml_dialog_open(self, open_: bool):
        # Wired to dialog.on_open_change so internal close events stay in sync.
        self.ml_dialog_open = bool(open_)

    @rx.event
    def set_ml_new_name(self, value: str):
        self.ml_new_name = value

    @rx.event
    def set_ml_new_type(self, value: str):
        self.ml_new_type = value

    @rx.event
    def set_ml_new_table(self, value: str):
        self.ml_new_table = value

    @rx.event(background=True)
    async def submit_new_model(self):
        # Snapshot form values and close the dialog FIRST so re-opens can't
        # overwrite our selections, then train against the snapshot.
        async with self:
            name = self.ml_new_name.strip()
            model_type = self.ml_new_type
            table_name = self.ml_new_table
            if not name:
                self.ml_train_status = "Please enter a model name."
                return
            self.ml_dialog_open = False
            self.ml_train_status = f"Training {model_type} on {table_name}…"

        try:
            from ato_app.ml.forecasters import quick_train
            result = quick_train(model_type, table_name)
        except Exception as e:
            async with self:
                self.ml_train_status = f"Training failed: {e}"
            return

        model_id = str(uuid.uuid4())
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO ml_models "
                    "(model_id, name, model_type, source_table, task, metric, "
                    "accuracy, mae, training_secs, created_at) "
                    "VALUES (:id, :name, :mt, :src, :task, :metric, "
                    ":acc, :mae, :secs, :ts)"
                ),
                {
                    "id": model_id,
                    "name": name,
                    "mt": result["model_type"],
                    "src": result["source_table"],
                    "task": result["task"],
                    "metric": result["metric"],
                    "acc": result["accuracy"],
                    "mae": result["mae"],
                    "secs": result["training_secs"],
                    "ts": dt.datetime.utcnow(),
                },
            )

        async with self:
            self._load_ml_models_from_db()
            self.ml_total = len(self.ml_models)
            self.ml_experiments_run = self.ml_total
            avg = sum(m["accuracy_num"] for m in self.ml_models) / len(self.ml_models)
            self.ml_avg_accuracy = f"{avg:.2f}%"
            self.ml_train_status = (
                f"✓ {result['model_type']} on {result['source_table']} — "
                f"accuracy {result['accuracy']:.2f}% "
                f"({result['training_secs']:.2f}s, {result['n_rows']:,} rows)"
            )

    @rx.event(background=True)
    async def retrain_model(self, model_id: str):
        """Re-train a single model in place against its original source table."""
        async with self:
            self.ml_busy_model = model_id
            target = next((m for m in self.ml_models if m["model_id"] == model_id), None)
            if target is None:
                self.ml_busy_model = ""
                return
            model_type = target["model_type"]
            source_table = target.get("source_table") or "revenue_timeseries"

        try:
            from ato_app.ml.forecasters import quick_train
            result = quick_train(model_type, source_table)
        except Exception as e:
            async with self:
                self.ml_train_status = f"Retrain failed: {e}"
                self.ml_busy_model = ""
            return

        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE ml_models SET model_type=:mt, accuracy=:acc, "
                    "mae=:mae, training_secs=:secs, task=:task, metric=:metric "
                    "WHERE model_id=:id"
                ),
                {
                    "id": model_id,
                    "mt": result["model_type"],
                    "acc": result["accuracy"],
                    "mae": result["mae"],
                    "secs": result["training_secs"],
                    "task": result["task"],
                    "metric": result["metric"],
                },
            )

        async with self:
            self._load_ml_models_from_db()
            avg = sum(m["accuracy_num"] for m in self.ml_models) / len(self.ml_models)
            self.ml_avg_accuracy = f"{avg:.2f}%"
            self.ml_busy_model = ""
            self.ml_train_status = (
                f"✓ Retrained on {source_table} — accuracy "
                f"{result['accuracy']:.2f}%"
            )

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    @rx.event
    def set_bound_table(self, table_name: str):
        if table_name == self.bound_table:
            return
        self.bound_table = table_name
        self.specialist_messages = []
        _reset_agent(table_name)

    @rx.event
    def set_home_chat_input(self, value: str):
        self.home_chat_input = value

    @rx.event
    def set_specialist_chat_input(self, value: str):
        self.specialist_chat_input = value

    async def _stream_response(
        self, agent, user_msg: str, msgs_attr: str, busy_attr: str
    ):
        """Shared streaming routine for both chat panels.

        Reads/writes the messages list named by `msgs_attr` and the busy flag
        named by `busy_attr` so the home + specialist panels stay isolated.
        """
        full_text = ""
        stream_failed = False
        try:
            async for event in agent.stream_async(user_msg):
                chunk = ""
                if isinstance(event, dict):
                    chunk = event.get("data", "") or ""
                if not chunk:
                    continue
                full_text += chunk
                async with self:
                    msgs = list(getattr(self, msgs_attr))
                    msgs[-1] = {"role": "assistant", "content": full_text}
                    setattr(self, msgs_attr, msgs)
        except Exception:
            stream_failed = True
            full_text = ""

        if stream_failed or not full_text:
            try:
                full_text = str(agent(user_msg))
            except Exception as e:
                full_text = self._format_agent_error(e)

        async with self:
            msgs = list(getattr(self, msgs_attr))
            msgs[-1] = {
                "role": "assistant",
                "content": full_text or "(no response from model)",
            }
            setattr(self, msgs_attr, msgs)
            setattr(self, busy_attr, False)

    @rx.event(background=True)
    async def submit_home_chat(self):
        """Send a message to the orchestrator on the home page."""
        async with self:
            if not self.home_chat_input.strip() or self.home_chat_busy:
                return
            user_msg = self.home_chat_input.strip()
            self.home_messages = self.home_messages + [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": ""},
            ]
            self.home_chat_input = ""
            self.home_chat_busy = True

        try:
            agent = _orchestrator()
        except Exception as e:
            async with self:
                msgs = list(self.home_messages)
                msgs[-1] = {
                    "role": "assistant",
                    "content": f"Failed to build orchestrator: {e}",
                }
                self.home_messages = msgs
                self.home_chat_busy = False
            return

        await self._stream_response(
            agent, user_msg, "home_messages", "home_chat_busy"
        )

    @rx.event(background=True)
    async def submit_specialist_chat(self):
        """Send a message to the single-table specialist on /chat/[agent_id]."""
        async with self:
            if (not self.specialist_chat_input.strip()
                    or self.specialist_chat_busy):
                return
            user_msg = self.specialist_chat_input.strip()
            self.specialist_messages = self.specialist_messages + [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": ""},
            ]
            self.specialist_chat_input = ""
            self.specialist_chat_busy = True
            bound = self.bound_table

        try:
            agent = _agent_for(bound)
        except Exception as e:
            async with self:
                msgs = list(self.specialist_messages)
                msgs[-1] = {
                    "role": "assistant",
                    "content": f"Failed to build specialist agent: {e}",
                }
                self.specialist_messages = msgs
                self.specialist_chat_busy = False
            return

        await self._stream_response(
            agent, user_msg, "specialist_messages", "specialist_chat_busy"
        )

    @staticmethod
    def _format_currency(value: float) -> str:
        if value >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"${value / 1_000:.0f}k"
        return f"${value:,.0f}"

    @staticmethod
    def _format_agent_error(err: Exception) -> str:
        text = str(err)
        if "credit balance is too low" in text.lower():
            return (
                "⚠️ Anthropic API rejected the request: your account has no "
                "credit. Top up at https://console.anthropic.com/settings/billing "
                "and try again."
            )
        if "invalid x-api-key" in text.lower() or "invalid api key" in text.lower():
            return (
                "⚠️ The API key in .env is not valid. Verify CLAUDE_API_KEY."
            )
        return f"⚠️ {type(err).__name__}: {text}"

    # ------------------------------------------------------------------
    # Create Agent form
    # ------------------------------------------------------------------

    @rx.event
    def open_agent_dialog(self):
        self.new_agent_name = ""
        self.new_agent_table = "customers"
        self.new_agent_description = ""
        self.new_agent_persona = ""
        self.agent_dialog_open = True

    @rx.event
    def close_agent_dialog(self):
        self.agent_dialog_open = False

    @rx.event
    def set_agent_dialog_open(self, open_: bool):
        self.agent_dialog_open = bool(open_)

    @rx.event
    def set_new_agent_name(self, value: str):
        self.new_agent_name = value

    @rx.event
    def set_new_agent_description(self, value: str):
        self.new_agent_description = value

    @rx.event
    def set_new_agent_table(self, value: str):
        self.new_agent_table = value

    @rx.event
    def set_new_agent_persona(self, value: str):
        self.new_agent_persona = value

    @rx.event
    def load_chat_agent(self):
        agent_id = self.router._page.params.get("agent_id", "")
        if not agent_id:
            return
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT agent_id, name, table_name, description, persona, "
                    "created_at FROM agents WHERE agent_id = :id"
                ),
                {"id": agent_id},
            ).first()
        if row is None:
            self.chat_agent_id = ""
            self.chat_agent_name = "(unknown agent)"
            self.chat_agent_description = ""
            self.chat_agent_persona = ""
            self.chat_agent_created = ""
            self.chat_agent_capability = ""
            return
        aid, name, table_name, description, persona, created_at = row
        # Only reset the conversation thread when switching to a different
        # agent — refreshing the same agent keeps the history.
        if self.chat_agent_id != aid:
            self.specialist_messages = []
        self.chat_agent_id = aid
        self.chat_agent_name = name
        self.chat_agent_description = description or ""
        self.chat_agent_persona = persona or ""
        self.chat_agent_created = str(created_at)[:10]
        self.chat_agent_capability = _CAPABILITY_BY_TABLE.get(
            table_name,
            "Specialist agent bound to a single table.",
        )
        self.bound_table = table_name
        _reset_agent(table_name, persona or "")

    @rx.event
    def submit_new_agent(self):
        if not self.new_agent_name.strip():
            return
        agent_id = str(uuid.uuid4())
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO agents "
                    "(agent_id, name, table_name, description, persona, created_at) "
                    "VALUES (:id, :name, :tbl, :desc, :persona, :ts)"
                ),
                {
                    "id": agent_id,
                    "name": self.new_agent_name.strip(),
                    "tbl": self.new_agent_table,
                    "desc": self.new_agent_description.strip(),
                    "persona": self.new_agent_persona.strip(),
                    "ts": dt.datetime.utcnow(),
                },
            )
        self.bound_table = self.new_agent_table
        # Fresh thread for the newly-created agent's chat page.
        self.specialist_messages = []
        _reset_agent(self.new_agent_table, self.new_agent_persona.strip())
        self.new_agent_name = ""
        self.new_agent_description = ""
        self.new_agent_persona = ""
        self.agent_dialog_open = False
        return rx.redirect(f"/chat/{agent_id}")
