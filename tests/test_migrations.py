"""Alembic migrations build the same schema as the ORM models, and roll back cleanly."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from lacuna.config import Settings
from lacuna.db.models import Base
from lacuna.db.session import make_engine

ROOT = Path(__file__).resolve().parent.parent


def test_upgrade_matches_models_and_downgrades(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LACUNA_DATABASE_URL", settings.database_url)
    engine = make_engine(settings.database_url)
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations drifted: {diff}"

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
