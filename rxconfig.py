import reflex as rx
from reflex.plugins import RadixThemesPlugin

config = rx.Config(
    app_name="ato_app",
    db_url="sqlite:///data/app.db",
    frontend_port=3000,
    backend_port=8000,
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
