"""Sticky top bar — matches the three reference screenshots.

Left:  page title + subtitle
Right: org switcher (GF), FY pill, Export button, bell icon, PL avatar
"""
from __future__ import annotations

import reflex as rx

from ato_app.theme import (
    CARD,
    CARD_BORDER,
    HEADER_HEIGHT,
    PILL_GRAY_BG,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def _org_switcher() -> rx.Component:
    return rx.hstack(
        rx.text("GF", font_weight="600", color=TEXT_PRIMARY, font_size="14px"),
        rx.icon("chevron-down", size=14, color=TEXT_MUTED),
        spacing="1",
        align="center",
        padding="6px 12px",
        border=f"1px solid {CARD_BORDER}",
        border_radius="8px",
        background=CARD,
        cursor="pointer",
    )


def _fy_pill() -> rx.Component:
    return rx.hstack(
        rx.icon("calendar", size=14, color=TEXT_MUTED),
        rx.text("FY 2025–2026", font_size="14px", color=TEXT_PRIMARY),
        spacing="2",
        align="center",
        padding="6px 12px",
        border=f"1px solid {CARD_BORDER}",
        border_radius="8px",
        background=CARD,
    )


def _export_button() -> rx.Component:
    return rx.hstack(
        rx.icon("download", size=14, color=TEXT_PRIMARY),
        rx.text("Export", font_size="14px", color=TEXT_PRIMARY),
        spacing="2",
        align="center",
        padding="6px 12px",
        border=f"1px solid {CARD_BORDER}",
        border_radius="8px",
        background=CARD,
        cursor="pointer",
    )


def _bell() -> rx.Component:
    return rx.box(
        rx.icon("bell", size=18, color=TEXT_MUTED),
        padding="6px",
        cursor="pointer",
    )


def _avatar() -> rx.Component:
    return rx.center(
        rx.text("PL", color="white", font_weight="600", font_size="12px"),
        width="32px",
        height="32px",
        border_radius="9999px",
        background="#3B82F6",
    )


def header(title: str, subtitle: str) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.heading(title, size="6", color=TEXT_PRIMARY, weight="bold"),
            rx.text(subtitle, color=TEXT_MUTED, font_size="14px"),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.hstack(
            _org_switcher(),
            _fy_pill(),
            _export_button(),
            _bell(),
            _avatar(),
            spacing="3",
            align="center",
        ),
        width="100%",
        height=HEADER_HEIGHT,
        padding="0 24px",
        background=CARD,
        border_bottom=f"1px solid {CARD_BORDER}",
        position="sticky",
        top="0",
        z_index="50",
        align="center",
    )
