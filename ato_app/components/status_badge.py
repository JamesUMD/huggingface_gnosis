"""Colored rounded pill — green / blue / gray / red based on status string.

Accepts either a plain string or a Reflex Var. Color is computed via
``rx.match`` so it stays reactive when bound to state.
"""
from __future__ import annotations

import reflex as rx

from ato_app.theme import (
    PILL_BLUE_BG,
    PILL_BLUE_FG,
    PILL_GRAY_BG,
    PILL_GRAY_FG,
    PILL_GREEN_BG,
    PILL_GREEN_FG,
    PILL_RED_BG,
    PILL_RED_FG,
)


def _bg_for(status: rx.Var | str) -> rx.Var | str:
    return rx.match(
        status,
        ("Running", PILL_GREEN_BG),
        ("Production", PILL_GREEN_BG),
        ("Active", PILL_GREEN_BG),
        ("Completed", PILL_GREEN_BG),
        ("Staging", PILL_BLUE_BG),
        ("Idle", PILL_GRAY_BG),
        ("Development", PILL_GRAY_BG),
        ("Failed", PILL_RED_BG),
        ("Needs Attention", PILL_RED_BG),
        PILL_GRAY_BG,
    )


def _fg_for(status: rx.Var | str) -> rx.Var | str:
    return rx.match(
        status,
        ("Running", PILL_GREEN_FG),
        ("Production", PILL_GREEN_FG),
        ("Active", PILL_GREEN_FG),
        ("Completed", PILL_GREEN_FG),
        ("Staging", PILL_BLUE_FG),
        ("Idle", PILL_GRAY_FG),
        ("Development", PILL_GRAY_FG),
        ("Failed", PILL_RED_FG),
        ("Needs Attention", PILL_RED_FG),
        PILL_GRAY_FG,
    )


def status_badge(status: rx.Var | str) -> rx.Component:
    return rx.box(
        rx.text(status, font_size="12px", font_weight="500"),
        background=_bg_for(status),
        color=_fg_for(status),
        padding="2px 10px",
        border_radius="9999px",
        display="inline-block",
    )
