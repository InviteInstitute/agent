"""Every setting the server reads from its environment, in one place. Each is read when it is
asked for, so a test can set a variable and see it take effect at once."""

import os


def text(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def number(name: str, default: float) -> float:
    raw = text(name)
    return float(raw) if raw else default


def flag(name: str, default: bool = False) -> bool:
    raw = text(name).lower()
    return raw in ("1", "true", "yes", "on") if raw else default


def database_url() -> str:
    url = text("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def environments() -> list[str]:
    """The coding environments this deployment serves, by id (ENVIRONMENTS=vexcode-vr,zany)."""
    return [name.strip() for name in text("ENVIRONMENTS", "vexcode-vr").split(",") if name.strip()]


def navigator_model() -> str:
    """The model students' replies come from, unless a researcher picks another."""
    return text("NAVIGATOR_MODEL", "qwen3.8-27b")


def avatar_enabled() -> bool:
    """Whether this deployment shows the 3D tutor and speaks its replies."""
    return flag("AVATAR_ENABLED")


def student_recency_hours() -> float:
    """How far back a fresh database's first log sync reaches, and which students the
    check-in daemon looks at: those with an event in this many hours."""
    return number("STUDENT_RECENCY_HOURS", 24.0)
