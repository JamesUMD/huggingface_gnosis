"""Three forecasters operating on the revenue_timeseries table.

Each one fits on the historical data, evaluates an in-sample MAE proxy on a
held-out tail (last 30 days), and forecasts the next ``horizon_days``.
"""
from __future__ import annotations

import datetime as dt
import warnings
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

from ato_app.db import engine

HOLDOUT_DAYS = 30


def _load_revenue() -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM revenue_timeseries ORDER BY date", engine)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["t"] = np.arange(len(df))
    df["dow"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


_FEATURES = ["t", "dow_sin", "dow_cos", "month_sin", "month_cos"]


def _future_frame(last_date: pd.Timestamp, last_t: int, horizon_days: int) -> pd.DataFrame:
    dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    df = pd.DataFrame({"date": dates})
    df["t"] = np.arange(last_t + 1, last_t + 1 + horizon_days)
    df["dow"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


def _sk_forecast(model_factory: Callable[[], object], horizon_days: int) -> dict:
    df = _add_features(_load_revenue())
    train = df.iloc[:-HOLDOUT_DAYS]
    holdout = df.iloc[-HOLDOUT_DAYS:]

    model = model_factory()
    model.fit(train[_FEATURES], train["revenue_usd"])
    holdout_pred = model.predict(holdout[_FEATURES])
    mae = float(mean_absolute_error(holdout["revenue_usd"], holdout_pred))

    # refit on full history for the forward forecast
    model = model_factory()
    model.fit(df[_FEATURES], df["revenue_usd"])
    future = _future_frame(df["date"].iloc[-1], int(df["t"].iloc[-1]), horizon_days)
    preds = model.predict(future[_FEATURES])

    return {
        "model": model_factory.__name__.replace("_make_", ""),
        "dates": [d.date().isoformat() for d in future["date"]],
        "predictions": [float(round(p, 2)) for p in preds],
        "mae": round(mae, 2),
    }


def _make_linear() -> LinearRegression:
    return LinearRegression()


def _make_random_forest() -> RandomForestRegressor:
    return RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)


def _arima_forecast(horizon_days: int) -> dict:
    from statsmodels.tsa.arima.model import ARIMA

    df = _load_revenue().set_index("date")
    series = df["revenue_usd"].asfreq("D")

    train = series.iloc[:-HOLDOUT_DAYS]
    holdout = series.iloc[-HOLDOUT_DAYS:]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = ARIMA(train, order=(2, 1, 2)).fit()
        holdout_pred = fitted.forecast(steps=HOLDOUT_DAYS)
        mae = float(mean_absolute_error(holdout, holdout_pred))

        full = ARIMA(series, order=(2, 1, 2)).fit()
        future = full.forecast(steps=horizon_days)

    last_date = series.index[-1]
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    return {
        "model": "arima",
        "dates": [d.date().isoformat() for d in future_dates],
        "predictions": [float(round(p, 2)) for p in future.values],
        "mae": round(mae, 2),
    }


def run_forecast(model: str, horizon_days: int = 30) -> dict:
    m = (model or "").lower().replace("-", "_")
    if m in {"linear", "linear_regression", "linreg"}:
        return _sk_forecast(_make_linear, horizon_days)
    if m in {"random_forest", "rf", "randomforest"}:
        return _sk_forecast(_make_random_forest, horizon_days)
    if m in {"arima"}:
        return _arima_forecast(horizon_days)
    return {"error": f"Unknown model: {model}. Use linear, random_forest, or arima."}


def _accuracy_from_mae(mae: float, mean_target: float) -> float:
    """Map MAE to a 0-100 'accuracy' for display (clamped to [60, 99.5])."""
    if mean_target <= 0:
        return 70.0
    pct_err = (mae / mean_target) * 100.0
    return float(max(60.0, min(99.5, 100.0 - pct_err)))


# ----------------------------------------------------------------------
# Per-table training profiles. Each defines the task + how to build X,y.
# ----------------------------------------------------------------------

_PROFILES: dict[str, dict] = {
    "revenue_timeseries": {
        "task": "regression",
        "label": "Predict daily revenue",
        "target": "revenue_usd",
    },
    "customers": {
        "task": "classification",
        "label": "Predict whether a customer is active (vs churned)",
        "target": "is_active",
    },
    "agent_telemetry": {
        "task": "classification",
        "label": "Predict an agent task's status",
        "target": "status",
    },
}


def available_tables() -> list[str]:
    return list(_PROFILES.keys())


def profile_for(table_name: str) -> dict:
    return _PROFILES[table_name]


def _build_xy(table_name: str):
    """Return (X_train, y_train, X_holdout, y_holdout, mean_target_or_None)."""
    import pandas as pd
    if table_name == "revenue_timeseries":
        df = _add_features(_load_revenue())
        train = df.iloc[:-HOLDOUT_DAYS]
        holdout = df.iloc[-HOLDOUT_DAYS:]
        return (
            train[_FEATURES], train["revenue_usd"],
            holdout[_FEATURES], holdout["revenue_usd"],
            float(df["revenue_usd"].mean()),
        )
    if table_name == "customers":
        df = pd.read_sql(
            "SELECT tier, industry, region, mrr_usd, seats, is_active "
            "FROM customers",
            engine,
        )
        # one-hot encode categoricals
        X = pd.get_dummies(
            df.drop(columns=["is_active"]),
            columns=["tier", "industry", "region"],
            drop_first=False,
        ).astype(float)
        y = df["is_active"].astype(int)
        # 80/20 split
        n = len(df)
        cut = int(n * 0.8)
        return X.iloc[:cut], y.iloc[:cut], X.iloc[cut:], y.iloc[cut:], None
    if table_name == "agent_telemetry":
        df = pd.read_sql(
            "SELECT agent_type, duration_ms, tokens_used, status "
            "FROM agent_telemetry",
            engine,
        )
        X = pd.get_dummies(
            df.drop(columns=["status"]),
            columns=["agent_type"],
            drop_first=False,
        ).astype(float)
        y = df["status"]
        n = len(df)
        cut = int(n * 0.8)
        return X.iloc[:cut], y.iloc[:cut], X.iloc[cut:], y.iloc[cut:], None
    raise ValueError(f"Unsupported training table: {table_name}")


def quick_train(model_type: str, table_name: str = "revenue_timeseries") -> dict:
    """Quick training pass against the given source table.

    model_type: "RandomForest", "XGBoost", or "AutoML" (best of the two).
    Returns dict with model_type, source_table, task, metric, accuracy, mae,
    training_secs, n_rows.
    """
    import time
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score
    from xgboost import XGBClassifier, XGBRegressor

    if table_name not in _PROFILES:
        raise ValueError(f"Unsupported table: {table_name}")

    task = _PROFILES[table_name]["task"]
    X_train, y_train, X_hold, y_hold, mean_target = _build_xy(table_name)

    if task == "regression":
        rf_factory = lambda: RandomForestRegressor(  # noqa: E731
            n_estimators=200, max_depth=8, n_jobs=-1, random_state=42
        )
        xgb_factory = lambda: XGBRegressor(  # noqa: E731
            n_estimators=300, max_depth=6, learning_rate=0.08,
            n_jobs=-1, random_state=42, verbosity=0,
        )

        def fit_eval(make):
            t0 = time.perf_counter()
            m = make()
            m.fit(X_train, y_train)
            pred = m.predict(X_hold)
            mae = float(mean_absolute_error(y_hold, pred))
            return mae, time.perf_counter() - t0

        score_key = "mae"
        better = lambda a, b: a <= b  # noqa: E731  (lower MAE wins)
    else:  # classification
        # Encode label to ints for XGBoost (it requires numeric targets).
        from sklearn.preprocessing import LabelEncoder
        le = LabelEncoder()
        y_train_enc = le.fit_transform(y_train)
        y_hold_enc = le.transform(y_hold)
        n_classes = len(le.classes_)

        rf_factory = lambda: RandomForestClassifier(  # noqa: E731
            n_estimators=200, max_depth=8, n_jobs=-1, random_state=42
        )
        xgb_factory = lambda: XGBClassifier(  # noqa: E731
            n_estimators=300, max_depth=6, learning_rate=0.08,
            n_jobs=-1, random_state=42, verbosity=0,
            objective="binary:logistic" if n_classes == 2 else "multi:softprob",
            num_class=None if n_classes == 2 else n_classes,
        )

        def fit_eval(make):
            t0 = time.perf_counter()
            m = make()
            m.fit(X_train, y_train_enc)
            pred = m.predict(X_hold)
            acc = float(accuracy_score(y_hold_enc, pred))
            return acc, time.perf_counter() - t0

        score_key = "accuracy"
        better = lambda a, b: a >= b  # noqa: E731

    mt = model_type.replace(" ", "").lower()
    if mt in ("randomforest", "rf"):
        score, secs = fit_eval(rf_factory)
        chosen = "RandomForest"
    elif mt in ("xgboost", "xgb"):
        score, secs = fit_eval(xgb_factory)
        chosen = "XGBoost"
    else:
        rf_score, rf_s = fit_eval(rf_factory)
        xgb_score, xgb_s = fit_eval(xgb_factory)
        if better(rf_score, xgb_score):
            score, secs, chosen = rf_score, rf_s + xgb_s, "AutoML (RandomForest)"
        else:
            score, secs, chosen = xgb_score, rf_s + xgb_s, "AutoML (XGBoost)"

    if task == "regression":
        accuracy_pct = round(_accuracy_from_mae(score, mean_target or 0.0), 2)
        mae_val = round(score, 2)
    else:
        accuracy_pct = round(score * 100.0, 2)
        mae_val = 0.0  # not applicable

    return {
        "model_type": chosen,
        "source_table": table_name,
        "task": task,
        "metric": score_key,
        "accuracy": accuracy_pct,
        "mae": mae_val,
        "training_secs": round(secs, 2),
        "n_rows": int(len(X_train) + len(X_hold)),
    }


def revenue_recent(days: int = 30) -> list[dict]:
    """Last N days of (date, revenue_usd) for the small dashboard chart."""
    df = pd.read_sql(
        f"SELECT date, revenue_usd FROM revenue_timeseries "
        f"ORDER BY date DESC LIMIT {int(days)}",
        engine,
    )
    df = df.iloc[::-1].reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df.to_dict(orient="records")
