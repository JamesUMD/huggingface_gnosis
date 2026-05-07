"""Small uppercase label, large bold number underneath."""
from __future__ import annotations

import reflex as rx

from ato_app.theme import (
    CARD,
    CARD_BORDER,
    CARD_RADIUS,
    CARD_SHADOW,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def metric_card(
    label: str,
    value: rx.Var | str | int,
    *,
    sublabel: str | None = None,
    accent_icon: str | None = None,
) -> rx.Component:
    head = rx.hstack(
        rx.text(
            label,
            font_size="12px",
            color=TEXT_MUTED,
            letter_spacing="0.04em",
            text_transform="uppercase",
        ),
        rx.spacer(),
        rx.cond(
            accent_icon is not None,
            rx.icon(accent_icon or "circle", size=14, color=TEXT_MUTED),
            rx.fragment(),
        ),
        align="center",
        width="100%",
    )

    return rx.vstack(
        head,
        rx.text(value, font_size="28px", font_weight="700", color=TEXT_PRIMARY),
        rx.cond(
            sublabel is not None,
            rx.text(sublabel or "", font_size="12px", color=TEXT_MUTED),
            rx.fragment(),
        ),
        spacing="1",
        align="start",
        background=CARD,
        border=f"1px solid {CARD_BORDER}",
        border_radius=CARD_RADIUS,
        box_shadow=CARD_SHADOW,
        padding="20px",
        width="100%",
    )
