---
title: AI Transformation Office
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# AI Transformation Office

A Reflex (Python) web app pairing a Strands-powered orchestrator agent with a metrics dashboard, backed by a synthetic SQLite database. The orchestrator routes questions to three specialist agents (customers, revenue, operations), and the ML Studio runs quick AutoML experiments (Random Forest vs XGBoost) against any of the source tables.

**Live demo (HF Spaces, Docker SDK):** https://JamesUMD23-ai-transformation-office.hf.space

## Quick start (one command)

```bash
python run.py
```

That script:

1. Creates `./venv` if it doesn't exist
2. Installs everything in `requirements.txt`
3. Seeds `data/app.db` with synthetic data (only on first run)
4. Runs `reflex init` (only on first run)
5. Launches `reflex run`

When it's running:

- Frontend → http://localhost:3000
- Backend → http://localhost:8000

Press **Ctrl+C** to stop.

### Useful flags

```bash
python run.py --reset-db  # drop and re-seed app.db
python run.py --no-run    # bootstrap only, don't start the app
```

## Prerequisites

- **Python 3.10+** (`python --version`)
- **An Anthropic-compatible API key** with credits — the chat won't return useful answers without one. See *API key* below.
- *(Optional)* **Graphviz** — only if you want to regenerate the architecture diagram via `python docs/architecture/generate.py`. Install with `winget install Graphviz.Graphviz` on Windows.

## API key

Create a `.env` file in the project root with one of the following:

```
STRANDS_API_KEY=sk-ant-...
# or
ANTHROPIC_API_KEY=sk-ant-...
# or
CLAUDE_API_KEY=sk-ant-...
```

All three names work — the agent factory falls back across them. If the chat returns *"⚠️ Anthropic API rejected the request: your account has no credit"*, top up the account at https://console.anthropic.com/settings/billing.

## App tour

| Route | What's there |
|---|---|
| `/` | Executive Dashboard. Left: chat with the orchestrator (routes to specialists). Right: KPIs, 30-day revenue chart, customer mix by tier, top industries. |
| `/agent-core` | Lists user-created agents. **+ New Agent** dialog (name · bound table · description · persona). Click an agent name to open its detail page. |
| `/ml-studio` | Lists user-trained ML models. **+ New Model** dialog (name · source table · model type — RandomForest / XGBoost / **AutoML**). |
| `/chat/[agent_id]` | Single-agent detail + chat. Shows description, capability, bound table, persona, and a streaming chat with the specialist. |

### Architecture

![System architecture](ato_architecture.png)

Regenerate it with:

```bash
python docs/architecture/generate.py
```

(Requires Graphviz.)

## What's in the database

Five tables seeded into `data/app.db`:

| Table | Rows | Purpose |
|---|---|---|
| `customers` | 1,000 | analytical (tier, industry, region, MRR, churn) |
| `revenue_timeseries` | ~1,096 | analytical (3 yrs daily revenue with trend + seasonality + noise) |
| `agent_telemetry` | 5,000 | synthetic seed only — **not used** by the orchestrator |
| `agents` | 0 (you fill it) | real created agents from the **Agent Core** tab |
| `ml_models` | 0 (you fill it) | real trained models from the **ML Studio** tab |

The orchestrator's three specialists:

- `customers_specialist` → reads `customers`
- `revenue_timeseries_specialist` → reads `revenue_timeseries`, can call the `forecast` tool
- `operations_specialist` → reads **your real** `agents` and `ml_models` (this is what answers *"what agents do I have running?"* — the synthetic `agent_telemetry` is intentionally excluded)

## Project layout

```
.
├── rxconfig.py                  # Reflex config
├── Dockerfile                   # HF Spaces / any Docker host (single-port)
├── run.py                       # one-command bootstrap + local launcher
├── requirements.txt
├── .env                         # your API key (gitignored)
├── .env.example                 # template
├── data/
│   ├── seed.py                  # builds + seeds app.db
│   └── app.db                   # generated
├── ato_app/
│   ├── ato_app.py               # rx.App entry, registers routes
│   ├── state.py                 # global Reflex State
│   ├── db.py                    # SQLAlchemy engine + auto-seed/migrate
│   ├── theme.py                 # design tokens
│   ├── components/              # header, metric_card, status_badge, hero_icon
│   ├── pages/                   # home, agent_core, ml_studio, chat
│   ├── agents/factory.py        # build_orchestrator_agent / build_agent_for_table
│   ├── agents/tools.py          # run_sql, describe_table, forecast
│   └── ml/forecasters.py        # linear / RF / ARIMA / AutoML
└── docs/architecture/generate.py # Graphviz diagram script
```

## Deploy to a public URL

This repo deploys to Hugging Face Spaces via the **Docker SDK** (the YAML at the top of this README sets `sdk: docker` and `app_port: 7860`).

1. Create a Space at https://huggingface.co/new-space
   - **SDK**: choose **Docker**
   - **Hardware**: CPU Basic (free) is enough
2. Push this repo to the Space's git remote:
   ```powershell
   git remote add hf https://huggingface.co/spaces/<your-user>/<space-name>
   git push hf main
   ```
3. In the Space's **Settings → Variables and secrets**, add a secret named `CLAUDE_API_KEY` (or `ANTHROPIC_API_KEY` / `STRANDS_API_KEY`) with your Anthropic key. **Never commit `.env`** — it's gitignored.
4. Spaces builds the container from the `Dockerfile` (~6–10 min for the first build because Reflex installs Node + builds the frontend bundle) and starts it with `reflex run --env=prod --single-port --backend-host=0.0.0.0 --backend-port=7860`.

The Space ends up at `https://<your-user>-<space-name>.hf.space`.

**Caveats**: free Spaces sleep after 48 h of inactivity. SQLite resets when the Space restarts (your created agents and trained models are lost) — paid hardware tiers or migrating to Postgres give you persistence.

### Self-host elsewhere

The same Dockerfile works on any container host (Render, Fly.io, EC2, GCP Cloud Run). Just:

```bash
docker build -t ato .
docker run -p 7860:7860 -e CLAUDE_API_KEY=sk-ant-... ato
```

## Troubleshooting

**Chat replies with `⚠️ Anthropic API rejected the request: your account has no credit`**
Top up at https://console.anthropic.com/settings/billing. The key is fine; the account is empty.

**`Address already in use` on ports 3000 / 8000**
Stop the previous instance, or change `frontend_port` / `backend_port` in `rxconfig.py`.

**ML Studio "+ New Model" trains but accuracy looks identical across runs of the same model type**
That's expected — all training is seeded with `random_state=42`, so the same `(model_type, source_table)` pair gives the same number every time. Different combinations *do* give different numbers.

**Diagram fails to render**
The `diagrams` library shells out to Graphviz's `dot.exe`. If the script can't find it, install Graphviz (`winget install Graphviz.Graphviz`) and restart your terminal so PATH picks it up.

## Manual setup (if you don't want to use `run.py`)

```bash
python -m venv venv
.\venv\Scripts\activate            # Windows
# source venv/bin/activate         # macOS/Linux
pip install -r requirements.txt
python data/seed.py                # only the first time
reflex init --template blank       # only the first time
reflex run
```

> Configuration reference: https://huggingface.co/docs/hub/spaces-config-reference
