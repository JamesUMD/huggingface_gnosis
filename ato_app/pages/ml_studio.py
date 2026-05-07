"""ML Studio page — only real, user-trained models. Includes a + New Model
dialog that runs a quick experiment (RandomForest, XGBoost, or AutoML)."""
from __future__ import annotations

import reflex as rx

from ato_app.components.header import header
from ato_app.components.hero_icon import hero_icon
from ato_app.components.metric_card import metric_card
from ato_app.state import State
from ato_app.theme import (
    BG,
    CARD,
    CARD_BORDER,
    CARD_RADIUS,
    CARD_SHADOW,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

MODEL_TYPES = ["AutoML", "RandomForest", "XGBoost"]
SOURCE_TABLES = ["revenue_timeseries", "customers", "agent_telemetry"]
TABLE_TASK_LABELS = {
    "revenue_timeseries": "regression — predict daily revenue",
    "customers": "classification — predict active vs churned",
    "agent_telemetry": "classification — predict task status",
}


def _nav() -> rx.Component:
    def link(label, href):
        return rx.link(
            rx.text(label, color=TEXT_MUTED, font_size="14px"),
            href=href,
            _hover={"color": TEXT_PRIMARY, "text_decoration": "none"},
        )
    return rx.hstack(
        link("Home", "/"),
        link("Agent Core", "/agent-core"),
        link("ML Studio", "/ml-studio"),
        spacing="5",
        padding="12px 24px",
        background=CARD,
        border_bottom=f"1px solid {CARD_BORDER}",
    )


def _table_header() -> rx.Component:
    return rx.hstack(
        rx.text("Model", font_size="13px", color=TEXT_MUTED, width="22%"),
        rx.text("Source", font_size="13px", color=TEXT_MUTED, width="20%"),
        rx.text("Type", font_size="13px", color=TEXT_MUTED, width="16%"),
        rx.text("Accuracy", font_size="13px", color=TEXT_MUTED, width="12%"),
        rx.text("MAE", font_size="13px", color=TEXT_MUTED, width="10%"),
        rx.text("Trained", font_size="13px", color=TEXT_MUTED, width="10%"),
        rx.text("", width="10%"),
        width="100%",
        padding="8px 0",
        border_bottom=f"1px solid {CARD_BORDER}",
    )


def _row(model) -> rx.Component:
    is_busy = State.ml_busy_model == model["model_id"]
    return rx.hstack(
        rx.text(model["name"], font_size="14px", color=TEXT_PRIMARY,
                font_weight="500", width="22%"),
        rx.text(model["source_table"], font_size="13px", color=TEXT_MUTED,
                width="20%", font_family="ui-monospace, SFMono-Regular, monospace"),
        rx.text(model["model_type"], font_size="14px", color=TEXT_MUTED, width="16%"),
        rx.text(model["accuracy"], font_size="14px", color=TEXT_PRIMARY, width="12%"),
        rx.text(model["mae"], font_size="14px", color=TEXT_MUTED, width="10%"),
        rx.text(model["training_secs"], font_size="14px", color=TEXT_MUTED, width="10%"),
        rx.box(
            rx.button(
                rx.cond(is_busy, "…", "Retrain"),
                size="2",
                variant="soft",
                disabled=is_busy,
                on_click=State.retrain_model(model["model_id"]),
            ),
            width="10%",
            text_align="right",
        ),
        width="100%",
        padding="12px 0",
        border_bottom=f"1px solid {CARD_BORDER}",
        align="center",
    )


def _empty_state() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.text(
                "No models trained yet.",
                font_size="14px",
                color=TEXT_PRIMARY,
                font_weight="500",
            ),
            rx.text(
                "Click \"+ New Model\" to run a quick experiment on the "
                "revenue timeseries.",
                font_size="13px",
                color=TEXT_MUTED,
                text_align="center",
            ),
            spacing="2",
            align="center",
        ),
        padding="32px",
        width="100%",
    )


def _new_model_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("New ML Model"),
            rx.dialog.description(
                "Train a quick experiment against the revenue_timeseries "
                "table. AutoML trains both Random Forest and XGBoost and "
                "keeps the better one.",
                size="2",
                color=TEXT_MUTED,
            ),
            rx.vstack(
                rx.vstack(
                    rx.text("Model name", font_size="13px",
                            color=TEXT_PRIMARY, font_weight="500"),
                    rx.input(
                        placeholder="e.g. Revenue Forecaster v1",
                        value=State.ml_new_name,
                        on_change=State.set_ml_new_name,
                        size="3",
                    ),
                    align="stretch",
                    spacing="1",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Source table", font_size="13px",
                            color=TEXT_PRIMARY, font_weight="500"),
                    rx.select(
                        SOURCE_TABLES,
                        value=State.ml_new_table,
                        on_change=State.set_ml_new_table,
                        size="3",
                    ),
                    rx.text(
                        rx.match(
                            State.ml_new_table,
                            ("revenue_timeseries", TABLE_TASK_LABELS["revenue_timeseries"]),
                            ("customers", TABLE_TASK_LABELS["customers"]),
                            ("agent_telemetry", TABLE_TASK_LABELS["agent_telemetry"]),
                            "",
                        ),
                        font_size="12px",
                        color=TEXT_MUTED,
                        font_style="italic",
                    ),
                    align="stretch",
                    spacing="1",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Model type", font_size="13px",
                            color=TEXT_PRIMARY, font_weight="500"),
                    rx.select(
                        MODEL_TYPES,
                        value=State.ml_new_type,
                        on_change=State.set_ml_new_type,
                        size="3",
                    ),
                    align="stretch",
                    spacing="1",
                    width="100%",
                ),
                rx.cond(
                    State.ml_train_status != "",
                    rx.text(
                        State.ml_train_status,
                        font_size="13px",
                        color=TEXT_MUTED,
                        font_style="italic",
                    ),
                    rx.fragment(),
                ),
                spacing="4",
                align="stretch",
                padding_top="12px",
                width="100%",
            ),
            rx.flex(
                rx.button(
                    "Cancel",
                    variant="soft",
                    color_scheme="gray",
                    on_click=State.close_new_model_dialog,
                ),
                rx.button(
                    "Train",
                    on_click=State.submit_new_model,
                ),
                spacing="3",
                justify="end",
                padding_top="16px",
            ),
            max_width="480px",
        ),
        open=State.ml_dialog_open,
        on_open_change=State.set_ml_dialog_open,
    )


def _last_status_strip() -> rx.Component:
    return rx.cond(
        State.ml_train_status != "",
        rx.box(
            rx.text(State.ml_train_status, font_size="13px", color=TEXT_MUTED),
            background="#F1F5F9",
            border_radius="8px",
            padding="8px 12px",
            width="100%",
        ),
        rx.fragment(),
    )


def ml_studio() -> rx.Component:
    return rx.box(
        header("ML Studio", "Model training, evaluation, and deployment"),
        _nav(),
        rx.box(
            rx.vstack(
                rx.center(hero_icon("flask-conical"), padding_bottom="8px"),
                rx.heading("ML Studio", size="6", color=TEXT_PRIMARY,
                           weight="bold", text_align="center"),
                rx.text("Model training, evaluation, and deployment",
                        color=TEXT_MUTED, font_size="14px", text_align="center"),
                rx.grid(
                    metric_card("Models Trained", State.ml_total),
                    metric_card("Experiments Run", State.ml_experiments_run),
                    metric_card("Avg Accuracy", State.ml_avg_accuracy),
                    columns="3",
                    spacing="3",
                    width="100%",
                    padding_top="12px",
                ),
                # + New Model button row
                rx.hstack(
                    rx.spacer(),
                    rx.button(
                        rx.icon("plus", size=14),
                        "New Model",
                        on_click=State.open_new_model_dialog,
                        size="2",
                    ),
                    width="100%",
                    align="center",
                ),
                _last_status_strip(),
                rx.cond(
                    State.ml_models.length() > 0,
                    rx.vstack(
                        _table_header(),
                        rx.foreach(State.ml_models, _row),
                        width="100%",
                        spacing="0",
                        align="stretch",
                    ),
                    _empty_state(),
                ),
                background=CARD,
                border=f"1px solid {CARD_BORDER}",
                border_radius=CARD_RADIUS,
                box_shadow=CARD_SHADOW,
                padding="32px",
                width="100%",
                spacing="3",
                align="stretch",
            ),
            padding="24px",
            max_width="1200px",
            margin="0 auto",
        ),
        _new_model_dialog(),
        background=BG,
        min_height="100vh",
        color=TEXT_PRIMARY,
        font_family="Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
    )
