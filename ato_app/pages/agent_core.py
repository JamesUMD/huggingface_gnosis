"""Agent Core page — mirrors ai_platform.png.

Lists user-created agents and exposes the New Agent dialog (the only entry
point for creating an agent).
"""
from __future__ import annotations

import reflex as rx

from ato_app.components.header import header
from ato_app.components.hero_icon import hero_icon
from ato_app.components.metric_card import metric_card
from ato_app.components.status_badge import status_badge
from ato_app.state import State, TABLES
from ato_app.theme import (
    BG,
    CARD,
    CARD_BORDER,
    CARD_RADIUS,
    CARD_SHADOW,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


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
        rx.text("Agent", font_size="13px", color=TEXT_MUTED, width="35%"),
        rx.text("Status", font_size="13px", color=TEXT_MUTED, width="20%"),
        rx.text("Bound Table", font_size="13px", color=TEXT_MUTED, width="25%"),
        rx.text("Created", font_size="13px", color=TEXT_MUTED, width="20%",
                text_align="right"),
        width="100%",
        padding="8px 0",
        border_bottom=f"1px solid {CARD_BORDER}",
    )


def _row(row) -> rx.Component:
    return rx.hstack(
        rx.link(
            rx.text(row["agent_name"], font_size="14px", color="#1E40AF",
                    font_weight="500"),
            href=row["detail_href"],
            width="35%",
            _hover={"text_decoration": "underline"},
        ),
        rx.box(status_badge(row["status"]), width="20%"),
        rx.text(row["bound_table"], font_size="14px", color=TEXT_MUTED,
                width="25%",
                font_family="ui-monospace, SFMono-Regular, monospace"),
        rx.text(row["created"], font_size="14px", color=TEXT_MUTED, width="20%",
                text_align="right"),
        width="100%",
        padding="12px 0",
        border_bottom=f"1px solid {CARD_BORDER}",
    )


def _empty_state() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.text(
                "No agents created yet.",
                font_size="14px",
                color=TEXT_PRIMARY,
                font_weight="500",
            ),
            rx.text(
                'Click "+ New Agent" to spin one up against a table.',
                font_size="13px",
                color=TEXT_MUTED,
            ),
            spacing="2",
            align="center",
        ),
        padding="32px",
        width="100%",
    )


def _new_agent_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("New Agent"),
            rx.dialog.description(
                "Create a specialist agent bound to one of the three tables. "
                "Optionally add a persona / extra system prompt.",
                size="2",
                color=TEXT_MUTED,
            ),
            rx.vstack(
                rx.vstack(
                    rx.text("Agent name", font_size="13px",
                            color=TEXT_PRIMARY, font_weight="500"),
                    rx.input(
                        placeholder="e.g. Customer Insights Agent",
                        value=State.new_agent_name,
                        on_change=State.set_new_agent_name,
                        size="3",
                    ),
                    align="stretch",
                    spacing="1",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Bound table", font_size="13px",
                            color=TEXT_PRIMARY, font_weight="500"),
                    rx.select(
                        TABLES,
                        value=State.new_agent_table,
                        on_change=State.set_new_agent_table,
                        size="3",
                    ),
                    align="stretch",
                    spacing="1",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Description",
                            font_size="13px", color=TEXT_PRIMARY,
                            font_weight="500"),
                    rx.text_area(
                        placeholder='Short description shown on the agent detail page. e.g. "Answers churn-related questions for the sales team."',
                        value=State.new_agent_description,
                        on_change=State.set_new_agent_description,
                        rows="3",
                    ),
                    align="stretch",
                    spacing="1",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Persona / extra system prompt",
                            font_size="13px", color=TEXT_PRIMARY,
                            font_weight="500"),
                    rx.text_area(
                        placeholder='Optional. Adds extra rules to the system prompt. e.g. "Focus on enterprise tier and quarterly trends."',
                        value=State.new_agent_persona,
                        on_change=State.set_new_agent_persona,
                        rows="4",
                    ),
                    align="stretch",
                    spacing="1",
                    width="100%",
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
                    on_click=State.close_agent_dialog,
                ),
                rx.button("Create", on_click=State.submit_new_agent),
                spacing="3",
                justify="end",
                padding_top="16px",
            ),
            max_width="480px",
        ),
        open=State.agent_dialog_open,
        on_open_change=State.set_agent_dialog_open,
    )


def agent_core() -> rx.Component:
    return rx.box(
        header("AI AgentCore Platform", "Autonomous AI agent deployment and monitoring"),
        _nav(),
        rx.box(
            rx.vstack(
                rx.center(hero_icon("bot"), padding_bottom="8px"),
                rx.heading("AI AgentCore Platform", size="6", color=TEXT_PRIMARY,
                           weight="bold", text_align="center"),
                rx.text("Autonomous AI agent deployment and monitoring",
                        color=TEXT_MUTED, font_size="14px", text_align="center"),
                rx.grid(
                    metric_card("Active Agents", State.agent_core_active),
                    metric_card("Tables Bound", State.agent_core_tables_bound),
                    metric_card("Latest Created", State.agent_core_latest),
                    columns="3",
                    spacing="3",
                    width="100%",
                    padding_top="12px",
                ),
                rx.hstack(
                    rx.spacer(),
                    rx.button(
                        rx.icon("plus", size=14),
                        "New Agent",
                        on_click=State.open_agent_dialog,
                        size="2",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.cond(
                    State.agent_core_rows.length() > 0,
                    rx.vstack(
                        _table_header(),
                        rx.foreach(State.agent_core_rows, _row),
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
        _new_agent_dialog(),
        background=BG,
        min_height="100vh",
        color=TEXT_PRIMARY,
        font_family="Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
    )
