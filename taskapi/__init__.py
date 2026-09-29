"""fe103-reference-api: a small task API for FE103 frontends, built the BE106 way."""
import os

from flask import Flask

from .commands import register_commands
from .config import get_config
from .errors import register_error_handlers
from .extensions import cors, db


def create_app(config_name=None):
    """Application factory.

    config_name is "development", "testing" or "production". When it is None
    (as with `flask --app taskapi run`), APP_CONFIG decides, default "development".
    """
    config = get_config(config_name)
    config.check()

    app = Flask(__name__)
    app.config.from_object(config)
    app.json.sort_keys = False  # keep JSON keys in the order the README shows

    db.init_app(app)
    cors.init_app(
        app,
        origins=app.config["CORS_ORIGINS"],
        allow_headers=["Authorization", "Content-Type"],
        methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    )

    from .routes import BLUEPRINTS
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    register_error_handlers(app)
    register_commands(app)

    if not app.testing and not os.environ.get("JWT_SECRET"):
        app.logger.warning("JWT_SECRET is not set; using an insecure development secret.")

    if app.config["CREATE_TABLES_ON_STARTUP"]:
        with app.app_context():
            db.create_all()  # kept simple on purpose; your BE106 API uses migrations

    return app
