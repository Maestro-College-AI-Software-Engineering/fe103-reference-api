import os

from dotenv import load_dotenv

# Read .env (if there is one) before any setting below is read.
load_dotenv()

DEFAULT_CORS_ORIGINS = "http://localhost:5173"  # the Vite dev server


def parse_origins(value):
    """Turn "http://a.com/, http://b.com" into ["http://a.com", "http://b.com"].

    Browsers send the Origin header without a trailing slash, so one here would
    never match. Spaces and trailing slashes are removed.
    """
    return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]


def normalize_database_url(url):
    """Use the psycopg 3 driver (the one in requirements.txt) for Postgres URLs.

    Hosts such as Render and Neon hand out URLs starting with postgres:// or
    postgresql://; SQLAlchemy needs postgresql+psycopg:// for psycopg 3.
    """
    if not url:
        return url
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _positive_int(name, default):
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise RuntimeError(f"{name} must be a whole number of 1 or more, got {raw!r}.")
    return value


class Config:
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get("DATABASE_URL"))
    JWT_SECRET = os.environ.get("JWT_SECRET")
    TOKEN_TTL_MINUTES = _positive_int("TOKEN_TTL_MINUTES", 60)
    CORS_ORIGINS = parse_origins(os.environ.get("CORS_ORIGINS") or DEFAULT_CORS_ORIGINS)
    CREATE_TABLES_ON_STARTUP = True
    MAX_CONTENT_LENGTH = 1024 * 1024  # 1 MB is plenty for JSON bodies

    @classmethod
    def check(cls):
        """Raise if a required setting is missing. Overridden per environment."""


class DevelopmentConfig(Config):
    # No DATABASE_URL? Use a SQLite file (Flask-SQLAlchemy puts it in instance/).
    SQLALCHEMY_DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI or "sqlite:///taskapi.db"
    # Convenience for local work only. ProductionConfig refuses to start without one.
    JWT_SECRET = Config.JWT_SECRET or "dev-only-secret-set-JWT_SECRET-in-your-env-file"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET = "testing-secret-that-is-at-least-32-bytes-long"
    TOKEN_TTL_MINUTES = 60
    CORS_ORIGINS = [DEFAULT_CORS_ORIGINS]
    CREATE_TABLES_ON_STARTUP = False  # the tests create and drop tables themselves


class ProductionConfig(Config):
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    @classmethod
    def check(cls):
        required = (
            ("DATABASE_URL", cls.SQLALCHEMY_DATABASE_URI),
            ("JWT_SECRET", cls.JWT_SECRET),
        )
        missing = [name for name, value in required if not value]
        if missing:
            raise RuntimeError(
                "Missing required environment variable(s): " + ", ".join(missing)
            )


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(config_name=None):
    """Pick a config class by name, or from APP_CONFIG (default: development)."""
    name = config_name or os.environ.get("APP_CONFIG") or "development"
    try:
        return CONFIGS[name]
    except KeyError:
        raise RuntimeError(
            f"Unknown config {name!r}. Use one of: {', '.join(CONFIGS)}."
        ) from None
