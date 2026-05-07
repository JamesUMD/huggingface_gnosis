"""Design tokens — keep these in sync with the reference screenshots."""

BG = "#F5F5F7"
CARD = "#FFFFFF"
CARD_BORDER = "#E5E7EB"
CARD_RADIUS = "12px"
CARD_SHADOW = "0 1px 2px rgba(15, 23, 42, 0.04)"

TEXT_PRIMARY = "#0F172A"
TEXT_MUTED = "#64748B"

PILL_GREEN_BG = "#DCFCE7"
PILL_GREEN_FG = "#166534"
PILL_BLUE_BG = "#DBEAFE"
PILL_BLUE_FG = "#1E40AF"
PILL_GRAY_BG = "#F1F5F9"
PILL_GRAY_FG = "#475569"
PILL_RED_BG = "#FEE2E2"
PILL_RED_FG = "#991B1B"

HERO_ICON_BG = "#EEF2FF"
HERO_ICON_FG = "#4F46E5"

HEADER_HEIGHT = "64px"

CARD_STYLE = {
    "background": CARD,
    "border": f"1px solid {CARD_BORDER}",
    "border_radius": CARD_RADIUS,
    "box_shadow": CARD_SHADOW,
    "padding": "20px",
}

PAGE_STYLE = {
    "background": BG,
    "min_height": "100vh",
    "color": TEXT_PRIMARY,
    "font_family": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
}


def status_pill_colors(status: str) -> tuple[str, str]:
    s = (status or "").strip().lower()
    if s in {"running", "production", "active", "completed"}:
        return PILL_GREEN_BG, PILL_GREEN_FG
    if s in {"staging"}:
        return PILL_BLUE_BG, PILL_BLUE_FG
    if s in {"idle", "development"}:
        return PILL_GRAY_BG, PILL_GRAY_FG
    if s in {"failed", "needs attention"}:
        return PILL_RED_BG, PILL_RED_FG
    return PILL_GRAY_BG, PILL_GRAY_FG
