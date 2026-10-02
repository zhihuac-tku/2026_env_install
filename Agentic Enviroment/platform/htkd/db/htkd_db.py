 # py code beginning

"""HTKD-specific database helpers built on the shared NRI DB runtime."""

from __future__ import annotations

from sqlalchemy import Engine, text

from nri_code_core.db.db_runtime import (
    build_db_envs,
    get_engine,
    verify_database,
)


HTKD_DB_NAME = "htkd_db"
DEFAULT_ENV = "MacBook"


def get_htkd_engine(
    environment: str = DEFAULT_ENV,
) -> Engine:
    """
    Build and verify the HTKD SQLAlchemy engine using the
    shared nri_code_core database runtime.
    """
    environments = build_db_envs(HTKD_DB_NAME)

    if environment not in environments:
        raise ValueError(
            f"Unknown database environment: {environment}"
        )

    config = environments[environment]

    if config.get("mode") != "fixed_dsn":
        raise ValueError(
            "This command-line HTKD importer currently "
            "requires a fixed_dsn environment."
        )

    engine = get_engine(config["dsn"])

    # verify_database() checks against the runtime's configured DB_NAME,
    # so configure the shared runtime before verification.
    from nri_code_core.db.db_runtime import (
        configure_database_runtime,
    )

    configure_database_runtime(
        db_name=HTKD_DB_NAME,
        default_env=environment,
    )
    verify_database(engine)

    return engine


def create_import_batch(
    engine: Engine,
    *,
    dataset_version_id: int,
    source_checksum: str | None = None,
    import_program: str | None = None,
    notes: str | None = None,
) -> int:
    sql = text("""
        INSERT INTO control.import_batch (
            dataset_version_id,
            import_status,
            source_checksum,
            import_program,
            notes
        )
        VALUES (
            :dataset_version_id,
            'running',
            :source_checksum,
            :import_program,
            :notes
        )
        RETURNING import_batch_id
    """)

    with engine.begin() as conn:
        batch_id = conn.execute(
            sql,
            {
                "dataset_version_id": dataset_version_id,
                "source_checksum": source_checksum,
                "import_program": import_program,
                "notes": notes,
            },
        ).scalar_one()

    return int(batch_id)


def complete_import_batch(
    engine: Engine,
    *,
    import_batch_id: int,
    source_row_count: int,
    imported_row_count: int,
    rejected_row_count: int = 0,
) -> None:
    sql = text("""
        UPDATE control.import_batch
        SET
            completed_at = NOW(),
            import_status = 'completed',
            source_row_count = :source_row_count,
            imported_row_count = :imported_row_count,
            rejected_row_count = :rejected_row_count
        WHERE import_batch_id = :import_batch_id
    """)

    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "source_row_count": source_row_count,
                "imported_row_count": imported_row_count,
                "rejected_row_count": rejected_row_count,
                "import_batch_id": import_batch_id,
            },
        )


def fail_import_batch(
    engine: Engine,
    *,
    import_batch_id: int,
    error_message: str,
) -> None:
    sql = text("""
        UPDATE control.import_batch
        SET
            completed_at = NOW(),
            import_status = 'failed',
            notes = :error_message
        WHERE import_batch_id = :import_batch_id
    """)

    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "error_message": error_message[:5000],
                "import_batch_id": import_batch_id,
            },
        )


