---
title: AI Transformation Office
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.14.0
python_version: '3.13'
app_file: app.py
pinned: false
---

# AI Transformation Office

A Gradio web app pairing a Strands-powered orchestrator agent with a metrics dashboard, backed by a synthetic SQLite database. The orchestrator routes questions to three specialist agents (customers, revenue, operations), and the ML Studio runs quick AutoML experiments (Random Forest vs XGBoost) against any of the source tables.

## Quick start (one command)

```bash
python run.py
```

That script:

1. Creates `./venv` if it doesn't exist
2. Installs everything in `requirements.txt`
3. Seeds `data/app.db` with synthetic data (only on first run)
4. Launches the Gradio app

When it's running:

- Local URL → http://localhost:7860

Press **Ctrl+C** to stop.

### Useful flags

```bash
python run.py --share     # also expose a public *.gradio.live tunnel
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

The app is a single Gradio page with four tabs:

| Tab | What's there |
|---|---|
| **Dashboard** | Orchestrator chat (left) + KPIs / 30-day revenue chart / MRR-by-tier bar chart / top industries (right). |
| **Agent Core** | Lists all created agents in a table. **+ New Agent** form (name · bound table · description · persona). |
| **Chat with Agent** | Pick a created agent from a dropdown to load its details and have a conversation with that single-table specialist. |
| **ML Studio** | Lists all trained models. **+ New Model** form (name · source table · model type — RandomForest / XGBoost / **AutoML**). |

### Architecture

A rendered architecture diagram lives at `ato_architecture.png` (gitignored — generate it locally). Regenerate it with:

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
├── app.py                       # Gradio frontend (the entry point)
├── run.py                       # one-command bootstrap + launcher
├── requirements.txt
├── .env                         # your API key (gitignored)
├── .env.example                 # template
├── data/
│   ├── seed.py                  # builds + seeds app.db
│   └── app.db                   # generated
├── ato_app/                     # business logic (framework-agnostic)
│   ├── db.py                    # SQLAlchemy engine + auto-seed/migrate
│   ├── agents/factory.py        # build_orchestrator_agent / build_agent_for_table
│   ├── agents/tools.py          # run_sql, describe_table, forecast
│   └── ml/forecasters.py        # linear / RF / ARIMA / AutoML
├── docs/
│   ├── architecture/generate.py # Graphviz diagram script
│   └── screenshots/             # reference designs
└── ato_architecture.png         # rendered system diagram
```

## Deploy to a public URL

You have three easy paths.

### Option A — `--share` flag (fastest, no signup)

```bash
python run.py --share
```

Gradio uploads to its own tunnel service and prints a `https://<random>.gradio.live` URL valid for 72 hours. Best for quick demos.

**Caveats**: anonymous URL is publicly accessible while it's up; resets when you stop the process; not suitable for sensitive data.

### Option B — Hugging Face Spaces (free, persistent, public)

1. Create a new Space at https://huggingface.co/new-space
   - **SDK**: choose **Gradio**
   - **Space hardware**: free CPU is fine for this app
2. Push this repo to the Space's git remote:
   ```bash
   git remote add hf https://huggingface.co/spaces/<your-user>/<space-name>
   git push hf main
   ```
3. In the Space settings → **Variables and secrets**, add a secret named `CLAUDE_API_KEY` (or `ANTHROPIC_API_KEY` / `STRANDS_API_KEY`) with your Anthropic key. **Never commit `.env`** — that's why it's gitignored.
4. Spaces will auto-detect Gradio, install `requirements.txt`, and run `app.py`. First build takes ~3–5 minutes.

The space gets a permanent URL like `https://huggingface.co/spaces/<your-user>/<space-name>` and a direct embed at `https://<your-user>-<space-name>.hf.space`.

**Caveats**: free tier sleeps after 48 h of inactivity; SQLite resets every time the Space restarts (created agents and trained models are lost). For persistence, upgrade to a paid Space or migrate to Postgres.

### Option C — Self-host (Docker / VPS / Render / Fly.io)

The app is a single `python app.py` that listens on `$PORT` (default 7860). Any platform that runs Python can host it. Set `STRANDS_API_KEY` (or one of the alternates) as an environment variable. A minimal Dockerfile would be:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=7860
EXPOSE 7860
CMD ["python", "app.py"]
```

## Troubleshooting

**Chat replies with `⚠️ Anthropic API rejected the request: your account has no credit`**
Top up at https://console.anthropic.com/settings/billing. The key is fine; the account is empty.

**`Address already in use` on port 7860**
Stop the previous instance, or set `PORT=7861 python app.py`.

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
python app.py
```

> Configuration reference: https://huggingface.co/docs/hub/spaces-config-reference
