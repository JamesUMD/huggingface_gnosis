"""Home page: chat (left ~55%) + dashboard (right ~45%).

Stacks vertically below 1024px.
"""
from __future__ import annotations

import reflex as rx

from ato_app.components.header import header
from ato_app.components.metric_card import metric_card
from ato_app.components.status_badge import status_badge
from ato_app.state import State
from ato_app.theme import (
    BG,
    CARD,
    CARD_BORDER,
    CARD_RADIUS,
    CARD_SHADOW,
    PAGE_STYLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def _nav_link(label: str, href: str) -> rx.Component:
    return rx.link(
        rx.text(label, color=TEXT_MUTED, font_size="14px"),
        href=href,
        _hover={"color": TEXT_PRIMARY, "text_decoration": "none"},
    )


def _nav() -> rx.Component:
    return rx.hstack(
        _nav_link("Home", "/"),
        _nav_link("Agent Core", "/agent-core"),
        _nav_link("ML Studio", "/ml-studio"),
        spacing="5",
        padding="12px 24px",
        background=CARD,
        border_bottom=f"1px solid {CARD_BORDER}",
    )


def _message_bubble(msg: dict) -> rx.Component:
    is_user = msg["role"] == "user"
    return rx.hstack(
        rx.cond(is_user, rx.spacer(), rx.fragment()),
        rx.box(
            rx.text(
                msg["content"],
                white_space="pre-wrap",
                font_size="14px",
                color=rx.cond(is_user, "white", TEXT_PRIMARY),
            ),
            background=rx.cond(is_user, "#3B82F6", "#F1F5F9"),
            color=rx.cond(is_user, "white", TEXT_PRIMARY),
            padding="10px 14px",
            border_radius="12px",
            max_width="75%",
        ),
        rx.cond(is_user, rx.fragment(), rx.spacer()),
        width="100%",
        margin_y="6px",
    )


def _chat_panel() -> rx.Component:
    return rx.vstack(
        # Header row — orchestrator on home, single-table specialist on /chat/[id]
        rx.hstack(
            rx.vstack(
                rx.text("Conversation", font_weight="600", color=TEXT_PRIMARY),
                rx.cond(
                    State.use_orchestrator,
                    rx.text(
                        "Orchestrator agent — routes questions across "
                        "customers, revenue, and agent-fleet specialists.",
                        font_size="12px",
                        color=TEXT_MUTED,
                    ),
                    rx.text(
                        "Specialist agent bound to a single table.",
                        font_size="12px",
                        color=TEXT_MUTED,
                    ),
                ),
                spacing="0",
                align="start",
            ),
            rx.spacer(),
            rx.cond(
                State.use_orchestrator,
                rx.box(
                    rx.text(
                        "Orchestrator",
                        font_size="12px",
                        font_weight="500",
                        color="#1E40AF",
                    ),
                    background="#DBEAFE",
                    padding="2px 10px",
                    border_radius="9999px",
                    display="inline-block",
                ),
                rx.box(
                    rx.text(
                        State.bound_table,
                        font_size="12px",
                        font_weight="500",
                        color="#475569",
                    ),
                    background="#F1F5F9",
                    padding="2px 10px",
                    border_radius="9999px",
                    display="inline-block",
                ),
            ),
            width="100%",
            align="center",
            padding_bottom="12px",
            border_bottom=f"1px solid {CARD_BORDER}",
        ),
        # Messages
        rx.box(
            rx.cond(
                State.messages.length() == 0,
                rx.center(
                    rx.vstack(
                        rx.text(
                            "Ask anything across the three tables — the "
                            "orchestrator picks the right specialist.",
                            color=TEXT_MUTED,
                            font_size="13px",
                            text_align="center",
                        ),
                        rx.text(
                            'e.g. "How many enterprise finance customers '
                            'churned last quarter?" · "Forecast next 30 '
                            'days revenue with arima" · "Which agents '
                            'failed most often?"',
                            color=TEXT_MUTED,
                            font_size="12px",
                            text_align="center",
                            font_style="italic",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    height="100%",
                ),
                rx.foreach(State.messages, _message_bubble),
            ),
            flex="1",
            overflow_y="auto",
            padding="8px 4px",
            min_height="320px",
        ),
        # Input
        rx.form(
            rx.hstack(
                rx.input(
                    placeholder="Ask the agent…",
                    value=State.chat_input,
                    on_change=State.set_chat_input,
                    flex="1",
                    size="3",
                    disabled=State.chat_busy,
                ),
                rx.button(
                    rx.cond(State.chat_busy, "…", "Send"),
                    type="submit",
                    size="3",
                    disabled=State.chat_busy,
                ),
                width="100%",
                spacing="2",
            ),
            on_submit=State.submit_chat,
            width="100%",
            reset_on_submit=False,
        ),
        spacing="3",
        align="stretch",
        width="100%",
        height="560px",
        background=CARD,
        border=f"1px solid {CARD_BORDER}",
        border_radius=CARD_RADIUS,
        box_shadow=CARD_SHADOW,
        padding="16px",
    )


def _agent_row(row) -> rx.Component:
    return rx.hstack(
        rx.text(row["name"], font_size="13px", color=TEXT_PRIMARY,
                font_weight="500", width="45%",
                overflow="hidden", text_overflow="ellipsis"),
        rx.text(row["table_name"], font_size="12px", color=TEXT_MUTED,
                width="35%",
                font_family="ui-monospace, SFMono-Regular, monospace"),
        rx.text(row["created"], font_size="12px", color=TEXT_MUTED,
                width="20%", text_align="right"),
        width="100%",
        padding="8px 0",
        border_bottom=f"1px solid {CARD_BORDER}",
    )


def _model_row(row) -> rx.Component:
    return rx.hstack(
        rx.text(row["name"], font_size="13px", color=TEXT_PRIMARY,
                font_weight="500", width="35%",
                overflow="hidden", text_overflow="ellipsis"),
        rx.text(row["source_table"], font_size="12px", color=TEXT_MUTED,
                width="30%",
                font_family="ui-monospace, SFMono-Regular, monospace"),
        rx.text(row["accuracy"], font_size="13px", color=TEXT_PRIMARY,
                font_weight="500", width="15%"),
        rx.text(row["created"], font_size="12px", color=TEXT_MUTED,
                width="20%", text_align="right"),
        width="100%",
        padding="8px 0",
        border_bottom=f"1px solid {CARD_BORDER}",
    )


def _empty_panel(message: str, cta_label: str, cta_href: str) -> rx.Component:
    return rx.vstack(
        rx.text(message, font_size="13px", color=TEXT_MUTED, text_align="center"),
        rx.link(
            rx.button(cta_label, size="2", variant="soft"),
            href=cta_href,
        ),
        spacing="2",
        align="center",
        padding="16px 0",
    )


def _panel_card(title: str, count_label: str | rx.Var, body: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(title, font_weight="600", color=TEXT_PRIMARY),
            rx.spacer(),
            rx.text(count_label, font_size="12px", color=TEXT_MUTED),
            width="100%",
            padding_bottom="8px",
            border_bottom=f"1px solid {CARD_BORDER}",
        ),
        body,
        background=CARD,
        border=f"1px solid {CARD_BORDER}",
        border_radius=CARD_RADIUS,
        box_shadow=CARD_SHADOW,
        padding="20px",
        width="100%",
        spacing="2",
        align="stretch",
    )


def _tier_row(row) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(row["tier"], font_size="12px",
                    color=TEXT_PRIMARY, font_weight="500"),
            rx.spacer(),
            rx.text(row["count"], " · ", row["mrr_total"],
                    font_size="11px", color=TEXT_MUTED),
            width="100%",
        ),
        rx.box(
            rx.box(
                width=row["mrr_pct"].to_string() + "%",
                height="5px",
                background="#3B82F6",
                border_radius="3px",
            ),
            background="#F1F5F9",
            border_radius="3px",
            height="5px",
            width="100%",
        ),
        spacing="1",
        align="stretch",
        width="100%",
        padding="3px 0",
    )


def _industry_row(row) -> rx.Component:
    return rx.hstack(
        rx.text(row["industry"], font_size="13px", color=TEXT_PRIMARY,
                width="50%"),
        rx.text(row["count"], font_size="12px", color=TEXT_MUTED, width="22%"),
        rx.text(row["mrr_total"], font_size="13px", color=TEXT_PRIMARY,
                font_weight="500", width="28%", text_align="right"),
        width="100%",
        padding="6px 0",
        border_bottom=f"1px solid {CARD_BORDER}",
    )


def _compact_kpi(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(
            label,
            font_size="11px",
            color=TEXT_MUTED,
            letter_spacing="0.04em",
            text_transform="uppercase",
        ),
        rx.text(value, font_size="24px", font_weight="700",
                color=TEXT_PRIMARY, line_height="1.1"),
        spacing="1",
        align="start",
        background=CARD,
        border=f"1px solid {CARD_BORDER}",
        border_radius=CARD_RADIUS,
        box_shadow=CARD_SHADOW,
        padding="14px 16px",
        width="100%",
    )


def _compact_panel(title: str, sub: str | rx.Var, body: rx.Component,
                   *, padding: str = "14px") -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(title, font_weight="600", color=TEXT_PRIMARY,
                    font_size="14px"),
            rx.spacer(),
            rx.text(sub, font_size="12px", color=TEXT_MUTED),
            width="100%",
        ),
        body,
        background=CARD,
        border=f"1px solid {CARD_BORDER}",
        border_radius=CARD_RADIUS,
        box_shadow=CARD_SHADOW,
        padding=padding,
        width="100%",
        spacing="2",
        align="stretch",
    )


def _industry_compact(row) -> rx.Component:
    return rx.hstack(
        rx.text(row["industry"], font_size="13px", color=TEXT_PRIMARY,
                width="55%", overflow="hidden", text_overflow="ellipsis"),
        rx.text(row["mrr_total"], font_size="13px", color=TEXT_PRIMARY,
                font_weight="500", width="45%", text_align="right"),
        width="100%",
        padding="5px 0",
        border_bottom=f"1px solid {CARD_BORDER}",
    )


def _dashboard() -> rx.Component:
    return rx.vstack(
        # KPI row: 6 across (single row when wide enough)
        rx.grid(
            _compact_kpi("Active Agents", State.active_agents),
            _compact_kpi("Models Trained", State.models_trained),
            _compact_kpi("Avg Accuracy", State.avg_accuracy),
            _compact_kpi("Active Customers", State.total_customers),
            _compact_kpi("Total MRR", State.total_mrr),
            _compact_kpi("Churn Rate", State.churn_rate),
            columns="3",
            spacing="2",
            width="100%",
        ),
        # Row 1: Revenue chart  |  Customer Mix tier bars
        rx.grid(
            _compact_panel(
                "30-day Revenue",
                State.revenue_30d_delta,
                rx.vstack(
                    rx.text(State.revenue_30d, font_size="24px",
                            font_weight="700", color=TEXT_PRIMARY,
                            line_height="1.1"),
                    rx.recharts.line_chart(
                        rx.recharts.line(
                            data_key="revenue_usd",
                            type_="monotone",
                            stroke="#3B82F6",
                            stroke_width=2,
                            dot=False,
                        ),
                        rx.recharts.x_axis(data_key="date", hide=True),
                        rx.recharts.y_axis(hide=True),
                        rx.recharts.tooltip(),
                        data=State.revenue_chart,
                        height=90,
                        width="100%",
                    ),
                    spacing="2",
                    align="stretch",
                    width="100%",
                ),
            ),
            _compact_panel(
                "Customer Mix",
                "MRR by tier",
                rx.cond(
                    State.tier_breakdown.length() > 0,
                    rx.vstack(
                        rx.foreach(State.tier_breakdown, _tier_row),
                        width="100%",
                        spacing="0",
                        align="stretch",
                    ),
                    rx.text("No customer data.", font_size="12px",
                            color=TEXT_MUTED),
                ),
            ),
            columns="2",
            spacing="2",
            width="100%",
        ),
        # Row 2: Top Industries  |  Recent Activity
        rx.grid(
            _compact_panel(
                "Top Industries",
                "by MRR",
                rx.cond(
                    State.top_industries.length() > 0,
                    rx.vstack(
                        rx.foreach(State.top_industries, _industry_compact),
                        width="100%",
                        spacing="0",
                        align="stretch",
                    ),
                    rx.text("No data.", font_size="12px", color=TEXT_MUTED),
                ),
            ),
            _compact_panel(
                "Your Workbench",
                "agents · models",
                rx.vstack(
                    rx.hstack(
                        rx.text("Agents created", font_size="12px",
                                color=TEXT_MUTED),
                        rx.spacer(),
                        rx.text(State.active_agents,
                                font_size="14px", color=TEXT_PRIMARY,
                                font_weight="600"),
                        width="100%",
                    ),
                    rx.hstack(
                        rx.text("Models trained", font_size="12px",
                                color=TEXT_MUTED),
                        rx.spacer(),
                        rx.text(State.models_trained,
                                font_size="14px", color=TEXT_PRIMARY,
                                font_weight="600"),
                        width="100%",
                    ),
                    rx.hstack(
                        rx.link(
                            rx.button("Agent Core", size="1", variant="soft"),
                            href="/agent-core",
                        ),
                        rx.link(
                            rx.button("ML Studio", size="1", variant="soft"),
                            href="/ml-studio",
                        ),
                        spacing="2",
                        padding_top="6px",
                    ),
                    spacing="2",
                    align="stretch",
                    width="100%",
                ),
            ),
            columns="2",
            spacing="2",
            width="100%",
        ),
        spacing="2",
        align="stretch",
        width="100%",
    )


def home() -> rx.Component:
    return rx.box(
        header("Executive Dashboard", "AI Transformation Office · GF"),
        _nav(),
        rx.box(
            rx.flex(
                rx.box(_chat_panel(), flex="1", min_width="0"),
                rx.box(_dashboard(), flex="1.4", min_width="0"),
                spacing="3",
                wrap="wrap",
                width="100%",
            ),
            padding="16px",
        ),
        background=BG,
        min_height="100vh",
        color=TEXT_PRIMARY,
        font_family="Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
    )
