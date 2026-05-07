"""56x56 light-blue tinted hero icon block at top of feature pages."""
from __future__ import annotations

import reflex as rx

from ato_app.theme import HERO_ICON_BG, HERO_ICON_FG


def hero_icon(icon_name: str) -> rx.Component:
    return rx.center(
        rx.icon(icon_name, size=28, color=HERO_ICON_FG),
        width="56px",
        height="56px",
        background=HERO_ICON_BG,
        border_radius="12px",
    )
