"""rx.App entry — register all routes."""
from __future__ import annotations

import reflex as rx

from ato_app.pages.agent_core import agent_core
from ato_app.pages.chat import chat_page
from ato_app.pages.home import home
from ato_app.pages.ml_studio import ml_studio
from ato_app.state import State
from ato_app.theme import BG

app = rx.App(
    style={
        "background": BG,
        "font_family": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
    },
)

app.add_page(home, route="/", title="Executive Dashboard", on_load=State.load_dashboard)
app.add_page(agent_core, route="/agent-core", title="AI AgentCore Platform",
             on_load=State.load_agent_core)
app.add_page(ml_studio, route="/ml-studio", title="ML Studio",
             on_load=State.load_ml_studio)
app.add_page(chat_page, route="/chat/[agent_id]", title="Chat",
             on_load=State.load_chat_agent)
