from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import get_db_settings
from app.db.models import Base


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_db_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


# Indexes excluded from autogenerate / `alembic check` comparison.
#
# `uq_store_applications_active_owner_email` is a Postgres PARTIAL unique
# index. Alembic cannot round-trip its predicate: the model/migration declare
# `postgresql_where=text("status IN ('draft','submitted','pending_review',
# 'approved')")`, but Postgres reflects the predicate in its normalized form
# `status = ANY (ARRAY[...]::store_application_status)`. The two strings never
# match textually, so autogenerate emits a spurious `add_index` even though the
# DB index is present and correct. The index IS verified at the DB level by
# tests/test_store_applications_model.py::test_active_owner_email_index_exists_and_is_unique
# (existence + uniqueness) plus the C2 dedup/race tests (behavior).
#
# This exclusion is intentionally NAME-SCOPED to this one known false positive.
# Do NOT broaden it to all indexes or all partial indexes — that would hide
# real schema drift. Every other object stays under full `alembic check`.
_AUTOGEN_IGNORED_INDEXES = frozenset(
    {
        "uq_store_applications_active_owner_email",
    }
)


def _include_object(object_, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    """Exclude only the known partial-index false positive from comparison."""
    if type_ == "index" and name in _AUTOGEN_IGNORED_INDEXES:
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=_include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

