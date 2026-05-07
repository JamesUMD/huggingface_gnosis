import os

import reflex as rx
from reflex.plugins import RadixThemesPlugin

# When PORT is set (e.g. inside the Docker container on Hugging Face Spaces),
# use it for BOTH frontend and backend — `reflex run --single-port` requires
# the two values to match. Locally PORT is unset, so we use the standard
# 3000 / 8000 split.
_PORT = int(os.getenv("PORT", "0"))
_FRONTEND_PORT = _PORT or 3000
_BACKEND_PORT = _PORT or 8000

config = rx.Config(
    app_name="ato_app",
    db_url="sqlite:///data/app.db",
    frontend_port=_FRONTEND_PORT,
    backend_port=_BACKEND_PORT,
    plugins=[
        RadixThemesPlugin(
            theme=rx.theme(
                appearance="light",
                accent_color="blue",
                gray_color="slate",
                radius="medium",
            ),
        ),
    ],
)
