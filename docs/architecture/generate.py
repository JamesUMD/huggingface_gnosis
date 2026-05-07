"""Generate the AI Transformation Office architecture diagram (PNG).

Uses the `diagrams` Python library + Graphviz. The output is a single PNG
with three swim-lanes:

  Browser → Reflex App → Python Backend (orchestrator + specialists, ML, DB)

Run:
    venv\\Scripts\\python.exe docs\\architecture\\generate.py
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# Make sure Graphviz's `dot.exe` is on PATH for this process.
_GRAPHVIZ_BIN = r"C:\Program Files\Graphviz\bin"
if _GRAPHVIZ_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _GRAPHVIZ_BIN + os.pathsep + os.environ.get("PATH", "")
assert shutil.which("dot"), "Graphviz `dot` not found on PATH"

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EC2
from diagrams.aws.database import RDS
from diagrams.aws.ml import Sagemaker
from diagrams.generic.blank import Blank
from diagrams.onprem.client import User
from diagrams.programming.framework import React
from diagrams.programming.language import Python

# Render to the project root (alongside requirements.txt / instructions..md)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT = PROJECT_ROOT / "ato_architecture"

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "rankdir": "LR",
    "splines": "spline",
    "labelloc": "t",
    "pad": "0.4",
    "nodesep": "0.6",
    "ranksep": "0.9",
}

with Diagram(
    "AI Transformation Office — System Architecture",
    filename=str(OUT),
    show=False,
    direction="LR",
    outformat="png",
    graph_attr=graph_attr,
):
    # ------- Frontend -------
    user = User("Operator")
    with Cluster("Browser  (Reflex SPA, http://localhost:3000)"):
        ui_home = React("/  Home  (chat + dashboard)")
        ui_agents = React("/agent-core  (agents + dialog)")
        ui_ml = React("/ml-studio  (models + train dialog)")
        ui_chat = React("/chat/[agent_id]  (detail + chat)")

    # ------- Reflex backend -------
    with Cluster("Reflex Backend  (Python · Granian @ :8000)"):
        state = Python("rx.State\n(load_dashboard,\nsubmit_chat,\nsubmit_new_agent,\nsubmit_new_model)")
        factory = Python("agents/factory.py\n(build_orchestrator_agent)")
        forecasters = Python("ml/forecasters.py\nquick_train(model, table)")

    # ------- Strands agents layer -------
    with Cluster("Strands Agents  (Anthropic provider · claude-sonnet-4-6)"):
        orchestrator = EC2("Orchestrator\n(home page chat)")
        with Cluster("Specialist agents (as_tool)"):
            sp_customers = EC2("customers_specialist")
            sp_revenue = EC2("revenue_timeseries_specialist")
            sp_ops = EC2("operations_specialist\n(real agents + models)")
        with Cluster("Tools (read-only)"):
            t_run_sql = Blank("run_sql\n(SELECT only)")
            t_describe = Blank("describe_table")
            t_forecast = Blank("forecast\nlinear/RF/ARIMA")

    # ------- ML layer -------
    with Cluster("ML  (scikit-learn · XGBoost · statsmodels)"):
        rf = Sagemaker("RandomForest")
        xgb = Sagemaker("XGBoost")
        arima = Sagemaker("ARIMA")
        automl = Sagemaker("AutoML\n(picks the better\nof RF + XGB)")

    # ------- Storage -------
    with Cluster("SQLite  (data/app.db)"):
        t_customers = RDS("customers\n1,000 rows")
        t_revenue = RDS("revenue_timeseries\n1,096 rows")
        t_telemetry = RDS("agent_telemetry\n5,000 rows (synthetic)")
        t_agents = RDS("agents\n(real, user-created)")
        t_models = RDS("ml_models\n(real, user-trained)")

    # ---------- Edges ----------
    user >> ui_home
    user >> ui_agents
    user >> ui_ml
    user >> ui_chat

    # UI → State (websocket / event handlers)
    ui_home >> Edge(label="on_load,\nsubmit_chat") >> state
    ui_agents >> Edge(label="open dialog,\nsubmit_new_agent") >> state
    ui_ml >> Edge(label="open dialog,\nsubmit_new_model") >> state
    ui_chat >> Edge(label="load_chat_agent,\nsubmit_chat") >> state

    # State → factory → orchestrator
    state >> Edge(label="home: orchestrator\n/chat: specialist") >> factory
    factory >> Edge(label="builds") >> orchestrator
    orchestrator >> Edge(label="as_tool") >> sp_customers
    orchestrator >> Edge(label="as_tool") >> sp_revenue
    orchestrator >> Edge(label="as_tool") >> sp_ops

    # Specialists call tools
    sp_customers >> t_run_sql
    sp_customers >> t_describe
    sp_revenue >> t_run_sql
    sp_revenue >> t_forecast
    sp_ops >> t_run_sql
    sp_ops >> t_describe

    # Tool → DB
    t_run_sql >> Edge(label="SELECT only") >> t_customers
    t_run_sql >> t_revenue
    t_run_sql >> t_agents
    t_run_sql >> t_models
    t_describe >> t_customers
    t_describe >> t_revenue
    t_describe >> t_agents
    t_describe >> t_models

    # Forecast tool → forecasters → ML
    t_forecast >> forecasters
    forecasters >> rf
    forecasters >> xgb
    forecasters >> arima

    # ML Studio submit_new_model → quick_train → models
    state >> Edge(label="quick_train(model, table)", style="dashed") >> forecasters
    forecasters >> automl
    automl >> Edge(label="best") >> t_models

    # Create-agent submit → agents row
    state >> Edge(label="INSERT", style="dashed") >> t_agents

    # Dashboard loaders → DB (read for KPIs)
    state >> Edge(label="SELECT\nKPIs", color="darkgreen") >> t_customers
    state >> Edge(color="darkgreen") >> t_revenue
    state >> Edge(color="darkgreen") >> t_agents
    state >> Edge(color="darkgreen") >> t_models

print(f"Wrote {OUT.with_suffix('.png')}")
