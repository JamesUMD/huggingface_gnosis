"""Dynamic chat page at /chat/[agent_id] — shows full agent details and the
chat interface for talking to that single-table specialist."""
from __future__ import annotations

import reflex as rx

from ato_app.components.header import header
from ato_app.components.status_badge import status_badge
from ato_app.pages.home import _chat_panel, _nav_link
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


def _meta_field(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, font_size="11px", color=TEXT_MUTED,
                letter_spacing="0.04em", text_transform="uppercase"),
        rx.text(value, font_size="14px", color=TEXT_PRIMARY,
                font_weight="500"),
        spacing="0",
        align="start",
    )


def _detail_card() -> rx.Component:
    return rx.vstack(
        # Top row — name + status + back link
        rx.hstack(
            rx.vstack(
                rx.text(
                    "Agent",
                    font_size="11px",
                    color=TEXT_MUTED,
                    letter_spacing="0.04em",
                    text_transform="uppercase",
                ),
                rx.heading(
                    State.chat_agent_name,
                    size="6",
                    color=TEXT_PRIMARY,
                    weight="bold",
                ),
                spacing="0",
                align="start",
            ),
            rx.spacer(),
            status_badge("Active"),
            rx.link(
                rx.text("← Back to Agent Core",
                        font_size="13px", color=TEXT_MUTED),
                href="/agent-core",
                _hover={"color": TEXT_PRIMARY, "text_decoration": "none"},
            ),
            width="100%",
            align="center",
            spacing="3",
        ),
        # User-supplied description (only if set)
        rx.cond(
            State.chat_agent_description != "",
            rx.text(
                State.chat_agent_description,
                color=TEXT_PRIMARY,
                font_size="14px",
                line_height="1.5",
                padding_top="4px",
            ),
            rx.fragment(),
        ),
        # Auto-generated capability blurb (what the bound table can answer)
        rx.text(
            State.chat_agent_capability,
            color=TEXT_MUTED,
            font_size="13px",
            line_height="1.5",
            padding_top="4px",
        ),
        # Meta grid: bound table, created, agent id
        rx.grid(
            _meta_field(
                "Bound Table",
                rx.text(
                    State.bound_table,
                    font_size="14px",
                    color=TEXT_PRIMARY,
                    font_weight="500",
                    font_family="ui-monospace, SFMono-Regular, monospace",
                ),
            ),
            _meta_field("Created", State.chat_agent_created),
            _meta_field(
                "Agent ID",
                rx.text(
                    State.chat_agent_id,
                    font_size="12px",
                    color=TEXT_PRIMARY,
                    font_family="ui-monospace, SFMono-Regular, monospace",
                ),
            ),
            columns="3",
            spacing="4",
            width="100%",
            padding_top="12px",
        ),
        # Persona / system prompt (only if set)
        rx.cond(
            State.chat_agent_persona != "",
            rx.vstack(
                rx.text("Persona / extra system prompt",
                        font_size="11px", color=TEXT_MUTED,
                        letter_spacing="0.04em", text_transform="uppercase"),
                rx.box(
                    rx.text(
                        State.chat_agent_persona,
                        font_size="13px",
                        color=TEXT_PRIMARY,
                        white_space="pre-wrap",
                    ),
                    background="#F8FAFC",
                    border=f"1px solid {CARD_BORDER}",
                    border_radius="8px",
                    padding="10px 12px",
                    width="100%",
                ),
                spacing="1",
                align="stretch",
                width="100%",
                padding_top="12px",
            ),
            rx.fragment(),
        ),
        background=CARD,
        border=f"1px solid {CARD_BORDER}",
        border_radius=CARD_RADIUS,
        box_shadow=CARD_SHADOW,
        padding="24px",
        width="100%",
        spacing="2",
        align="stretch",
    )


def chat_page() -> rx.Component:
    return rx.box(
        header("Agent Detail", "Conversation with a configured agent"),
        _nav(),
        rx.box(
            rx.vstack(
                _detail_card(),
                _chat_panel(),
                spacing="3",
                align="stretch",
                max_width="900px",
                margin="0 auto",
                width="100%",
            ),
            padding="24px",
        ),
        background=BG,
        min_height="100vh",
        color=TEXT_PRIMARY,
        font_family="Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
    )
