# AI Transformation Office — Project Instructions

A multi-page Reflex web app that pairs a conversational Strands agent with a metrics dashboard, backed by a synthetic SQLite database. The visual language matches the three reference screenshots in `docs/screenshots/`.

---

## Tech Stack

- **App framework**: Reflex (Python) — the Reflex MCP server is attached; query it before guessing any API
- **Agent framework**: Strands Agents SDK — key is in `.env` as `STRANDS_API_KEY`
- **Database**: SQLite via SQLAlchemy, file at `data/app.db`, auto-seeded on first run
- **ML / forecasting**: scikit-learn, statsmodels (optional: prophet)
- **Synthetic data**: faker + numpy + pandas

---

## Reference Design

Three screenshots define the look (`docs/screenshots/dashboard.png`, `ai_platform.png`, `ml_studio.png`). Match exactly:

- Top bar: page title + subtitle (left) · org switcher (`GF ▾`), FY date pill (`📅 FY 2025–2026`), Export button, bell icon, `PL` avatar (right). Sticky, 64px tall.
- Soft gray page background, white rounded cards (12px radius, hairline border, subtle shadow).
- Metric cards: small uppercase label, large bold number underneath.
- Status pills: rounded, colored — green (Running/Production/Active), blue (Staging), gray (Idle/Development), red (Failed/Needs Attention).
- Hero icon block at top of feature cards: 56×56, light blue tint background, rounded 12px.

### Design tokens (use everywhere)

```
bg:           #F5F5F7
card:         #FFFFFF, border #E5E7EB, radius 12px
text primary: #0F172A
text muted:   #64748B
pill green:   bg #DCFCE7 / text #166534
pill blue:    bg #DBEAFE / text #1E40AF
pill gray:    bg #F1F5F9 / text #475569
pill red:     bg #FEE2E2 / text #991B1B
hero icon bg: #EEF2FF
```

---

## Database (synthetic, auto-seeded)

Three tables. If `data/app.db` doesn't exist on startup, run `data/seed.py` automatically.

### 1. `customers` — Q&A table (~1,000 rows)
For conversational queries like *"How many enterprise customers in finance churned last quarter?"*

| column | type | notes |
|---|---|---|
| customer_id | PK | uuid |
| name, industry, region, country | str | faker |
| tier | str | SMB / Mid-Market / Enterprise |
| signup_date, churn_date | date | churn_date nullable |
| mrr_usd, seats | float / int | |
| is_active | bool | |

### 2. `revenue_timeseries` — forecasting table (daily, 3 years)
For the regression playground. Inject trend + weekly/yearly seasonality + noise so models have real signal.

| column | notes |
|---|---|
| date (PK) | |
| revenue_usd | target variable |
| units_sold, marketing_spend, active_users | features |
| is_holiday, season, promo_active | features |

### 3. `agent_telemetry` — agent-task log (~5,000 rows)
Mirrors the AgentCore screenshot. One row per agent task.

| column | notes |
|---|---|
| task_id (PK) | |
| agent_name, agent_type | |
| status | Running / Idle / Failed / Completed |
| started_at, duration_ms, tokens_used | |
| input_summary, output_summary | short strings |

---

## Project Structure

```
project/
├── rxconfig.py
├── .env                       # STRANDS_API_KEY=...
├── requirements.txt
├── data/
│   ├── seed.py                # builds + seeds app.db
│   └── app.db                 # generated
├── ato_app/
│   ├── ato_app.py             # rx.App entry, routes
│   ├── state.py               # global Reflex State
│   ├── components/
│   │   ├── header.py          # top bar (match screenshots exactly)
│   │   ├── metric_card.py
│   │   ├── status_badge.py
│   │   └── data_table.py
│   ├── pages/
│   │   ├── home.py            # CHAT + DASHBOARD (main page)
│   │   ├── ml_studio.py       # mimics ml_studio.png
│   │   ├── agent_core.py      # mimics ai_platform.png
│   │   └── create_agent.py    # form to spin up a new agent on a table
│   ├── agents/
│   │   ├── factory.py         # build_agent_for_table(table_name) -> Agent
│   │   └── tools.py           # run_sql, describe_table, forecast
│   └── ml/
│       └── forecasters.py     # LinearReg, RandomForest, ARIMA wrappers
└── docs/
    └── screenshots/           # the three reference PNGs
```

---

## Main Page (Home) — Chat + Dashboard

Two-column layout: chat ~55% left, dashboard ~45% right. Stacks vertically below 1024px.

**Chat (left)**
- Thread with the active Strands agent (default bound to `customers`)
- Input at bottom, send on Enter, streaming response if Strands supports it, otherwise typing indicator
- Dropdown above the input to switch the agent's bound table → calls `build_agent_for_table` and resets the thread

**Dashboard (right)** — mimic the Executive Dashboard screenshot
- Top row: 4 metric cards — Active Agents, Tasks Processed, Avg Accuracy, Models in Production (all live from the DB)
- "Recent Agent Activity" table: last 5 rows of `agent_telemetry` with status pills
- Small 30-day revenue line chart from `revenue_timeseries`

---

## Other Pages

- **`/agent-core`** — mirrors `ai_platform.png`. Centered hero icon, 3 metric cards (Active Agents, Tasks Processed, Avg Uptime), agent table with Running/Idle pills. Pull all from `agent_telemetry`.
- **`/ml-studio`** — mirrors `ml_studio.png`. Centered flask icon, 3 metric cards (Models in Production, Experiments Run, Avg Accuracy), models table with Production/Staging/Development pills. Each row has a "Retrain" button that runs the corresponding forecaster against `revenue_timeseries` and updates accuracy.
- **`/create-agent`** — form: agent name, bound table (dropdown of 3 tables), persona/extra system prompt (textarea), Create button → persists config to an `agents` table and routes to `/chat/<agent_id>`.

---

## Agent Layer (Strands)

One factory, three tools, no hardcoded prompts per table.

```python
# ato_app/agents/factory.py
def build_agent_for_table(table_name: str, extra_persona: str = "") -> Agent:
    schema = get_schema(table_name)
    sample = get_sample(table_name, n=5)
    system_prompt = f"""
You are a data analyst agent for the `{table_name}` table.
Schema: {schema}
Sample rows: {sample}

Rules:
- Use run_sql for every data question. Never invent values.
- If the user asks for a forecast on revenue_timeseries, call forecast.
- Be concise. Show numbers, not preamble.

{extra_persona}
""".strip()
    return Agent(
        system_prompt=system_prompt,
        tools=[run_sql, describe_table, forecast],
    )
```

**Tools** (in `agents/tools.py`):
- `run_sql(query: str) -> list[dict]` — **read-only**: reject anything that isn't a SELECT, parameterize where possible
- `describe_table(name: str) -> dict` — returns `{columns, types, sample_rows}`
- `forecast(model: str, horizon_days: int) -> dict` — runs the named model against `revenue_timeseries`, returns `{dates, predictions, mae}`. Models: `linear`, `random_forest`, `arima`.

---

## Setup Steps

1. `pip install -r requirements.txt`
   (reflex, strands-agents, sqlalchemy, pandas, scikit-learn, statsmodels, faker, python-dotenv)
2. Ensure `.env` exists with `STRANDS_API_KEY=...`
3. `python data/seed.py` — creates `data/app.db` (also runs automatically on first app start if missing)
4. `reflex init` (first time only)
5. `reflex run` — local dev on port 3000
6. To expose to others: `reflex run --backend-host 0.0.0.0` or deploy via `reflex deploy`

---

## MCP Server Usage

The Reflex MCP server is attached. **Query it before writing any Reflex code** for:
- Component props (`rx.flex`, `rx.card`, `rx.data_table`, `rx.chat`-style patterns)
- State and event handler patterns (especially async handlers for streaming)
- Routing and page registration
- Theme overrides and conditional styling

Don't guess Reflex APIs — the version on disk is the source of truth.

---

## Done Definition

- [ ] `reflex run` boots the app cleanly
- [ ] `data/app.db` auto-seeds on first run
- [ ] Home page renders chat + live dashboard, styling matches screenshots
- [ ] Chat answers real questions against `customers` end-to-end
- [ ] Table switcher rebuilds the agent and clears the thread
- [ ] `/agent-core` and `/ml-studio` render with live DB data and match their screenshots
- [ ] `/create-agent` persists a new agent and routes to a working chat
- [ ] All status pills, metric cards, and the top header match the design tokens above
