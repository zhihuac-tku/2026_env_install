 # py code beginning

"""Read-only DBA evidence tools for a future ReAct investigator."""

from typing import Any

import pandas as pd

from nri_code_core.db.db_metadata import (
    get_all_columns,
    get_database_objects,
    get_foreign_keys,
    get_indexes,
    get_primary_keys,
    get_unique_constraints,
)
from nri_dba.dictionary import (
    get_column_dictionary_records,
    get_table_dictionary_record,
)
from nri_dba.relationship import (
    build_candidate_relationships_for_table,
    build_relationship_column_usage,
    build_relationship_impact_summary,
)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return df.where(pd.notna(df), None).to_dict(orient="records")


def _filter_table(df, schema_name="", table_name=""):
    if schema_name and "schema_name" in df.columns:
        df = df[df["schema_name"].astype(str).eq(schema_name)]
    if table_name and "table_name" in df.columns:
        df = df[df["table_name"].astype(str).eq(table_name)]
    return df


def inspect_database_objects(engine):
    """Read database-object metadata."""
    return _records(get_database_objects(engine))


def inspect_columns(engine, *, schema_name="", table_name=""):
    """Read physical-column metadata."""
    return _records(
        _filter_table(get_all_columns(engine), schema_name, table_name)
    )


def _column_name_from_record(record: dict[str, Any]) -> str:
    """Return a column name across the metadata shapes used by NRI."""
    for key in (
        "column_name",
        "source_column",
        "target_column",
        "foreign_column_name",
        "referenced_column",
    ):
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def inspect_columns_by_names(
    engine,
    *,
    column_names: list[str],
    max_records: int = 250,
):
    """Return only database columns whose names match selected target columns.

    This keeps relationship observations small even when the target database
    contains many tables and columns. The metadata reader may still inspect the
    catalog internally, but only the relevant matches are returned to the Agent.
    """
    wanted = {
        str(name).strip()
        for name in column_names
        if str(name).strip()
    }
    if not wanted:
        return []

    records = _records(get_all_columns(engine))
    matched = [
        record
        for record in records
        if _column_name_from_record(record) in wanted
    ]
    return matched[:max_records]


def inspect_primary_keys_by_column_names(
    engine,
    *,
    column_names: list[str],
    max_records: int = 250,
):
    """Return only PK metadata involving selected column names."""
    wanted = {
        str(name).strip()
        for name in column_names
        if str(name).strip()
    }
    if not wanted:
        return []

    records = _records(get_primary_keys(engine))
    matched = [
        record
        for record in records
        if _column_name_from_record(record) in wanted
    ]
    return matched[:max_records]


def inspect_primary_keys(engine, *, schema_name="", table_name=""):
    """Read primary-key metadata."""
    return _records(
        _filter_table(get_primary_keys(engine), schema_name, table_name)
    )


def inspect_foreign_keys(engine, *, schema_name="", table_name=""):
    """Read FK metadata; filtering is conservative when column names vary."""
    df = get_foreign_keys(engine)
    if not schema_name and not table_name:
        return _records(df)

    masks = []
    pairs = [
        ("schema_name", "table_name"),
        ("source_schema", "source_table"),
        ("target_schema", "target_table"),
        ("foreign_schema_name", "foreign_table_name"),
        ("referenced_schema", "referenced_table"),
    ]
    for schema_col, table_col in pairs:
        if table_col not in df.columns:
            continue
        mask = pd.Series(True, index=df.index)
        if schema_name and schema_col in df.columns:
            mask &= df[schema_col].astype(str).eq(schema_name)
        if table_name:
            mask &= df[table_col].astype(str).eq(table_name)
        masks.append(mask)

    if not masks:
        return _records(df)

    combined = masks[0]
    for mask in masks[1:]:
        combined |= mask
    return _records(df[combined])


def inspect_indexes(engine, *, schema_name="", table_name=""):
    """Read index metadata."""
    return _records(
        _filter_table(get_indexes(engine), schema_name, table_name)
    )


def inspect_unique_constraints(engine, *, schema_name="", table_name=""):
    """Read UNIQUE-constraint metadata."""
    return _records(
        _filter_table(get_unique_constraints(engine), schema_name, table_name)
    )


def inspect_table_dictionary(
    dictionary_engine,
    *,
    source_db,
    schema_name,
    table_name,
):
    """Read table-level NRI semantic dictionary evidence."""
    return get_table_dictionary_record(
        dictionary_engine, source_db, schema_name, table_name
    )


def inspect_column_dictionary(
    dictionary_engine,
    *,
    source_db,
    schema_name,
    table_name,
):
    """Read column-level NRI semantic dictionary evidence."""
    return _records(
        get_column_dictionary_records(
            dictionary_engine, source_db, schema_name, table_name
        )
    )


def analyze_relationship_candidates(
    *,
    all_columns,
    primary_keys,
    foreign_keys,
    schema_name,
    table_name,
):
    """Analyze candidate logical relationships from supplied evidence."""
    return _records(
        build_candidate_relationships_for_table(
            pd.DataFrame(all_columns),
            pd.DataFrame(primary_keys),
            pd.DataFrame(foreign_keys),
            schema_name,
            table_name,
        )
    )


def analyze_relationship_column_usage(
    *,
    all_columns,
    selected_columns,
):
    """Analyze selected-column usage across tables."""
    return _records(
        build_relationship_column_usage(
            pd.DataFrame(all_columns),
            pd.DataFrame(selected_columns),
        )
    )


def summarize_relationship_impact(
    *,
    incoming_foreign_keys,
    outgoing_foreign_keys,
    candidates,
):
    """Summarize deterministic relationship impact evidence."""
    return build_relationship_impact_summary(
        pd.DataFrame(incoming_foreign_keys),
        pd.DataFrame(outgoing_foreign_keys),
        pd.DataFrame(candidates),
    )

def inspect_enterprise_column_reference(
    target_engine,
    dictionary_engine,
    *,
    source_db: str,
    column_names: list[str],
    max_records: int = 500,
) -> dict[str, Any]:
    """Collect enterprise evidence for proposed column names.

    Returns physical column usage, PK usage, FK usage, and semantic
    dictionary records for the requested column names.

    This function reports observed evidence only. It does not decide
    whether a proposed column is good, bad, standard, or mandatory.
    """

    wanted = {
        str(name).strip().lower()
        for name in column_names
        if str(name).strip()
    }

    if not wanted:
        return {
            "column_names": [],
            "column_usage": [],
            "primary_key_usage": [],
            "foreign_key_usage": [],
            "dictionary_usage": [],
        }

    # --------------------------------------------------------
    # Physical column usage
    # --------------------------------------------------------
    all_column_records = _records(
        get_all_columns(
            target_engine
        )
    )

    column_usage = [
        record
        for record in all_column_records
        if str(
            record.get(
                "column_name",
                "",
            )
        ).strip().lower()
        in wanted
    ]

    # --------------------------------------------------------
    # Primary-key usage
    # --------------------------------------------------------
    all_pk_records = _records(
        get_primary_keys(
            target_engine
        )
    )

    primary_key_usage = [
        record
        for record in all_pk_records
        if _column_name_from_record(
            record
        ).strip().lower()
        in wanted
    ]

    # --------------------------------------------------------
    # Foreign-key usage
    # --------------------------------------------------------
    all_fk_records = _records(
        get_foreign_keys(
            target_engine
        )
    )

    foreign_key_usage = []

    for record in all_fk_records:

        source_column = str(
            record.get(
                "source_column",
                record.get(
                    "column_name",
                    "",
                ),
            )
            or ""
        ).strip().lower()

        target_column = str(
            record.get(
                "target_column",
                record.get(
                    "referenced_column",
                    "",
                ),
            )
            or ""
        ).strip().lower()

        if (
            source_column in wanted
            or target_column in wanted
        ):
            foreign_key_usage.append(
                record
            )

    # --------------------------------------------------------
    # Semantic dictionary usage
    # --------------------------------------------------------
    dictionary_usage = []

    try:
        dictionary_sql = """
        SELECT
            source_db,
            schema_name,
            table_name,
            column_name,
            business_name,
            description,
            data_role,
            semantic_type,
            allowed_values,
            example_values,
            join_hint,
            filter_hint,
            aggregation_hint,
            is_primary_key,
            is_foreign_key,
            verified
        FROM ai.data_dictionary
        WHERE source_db = :source_db
        ORDER BY
            column_name,
            verified DESC,
            schema_name,
            table_name
        """

        dictionary_df = pd.read_sql(
            dictionary_sql,
            dictionary_engine,
            params={
                "source_db": source_db,
            },
        )

        if not dictionary_df.empty:

            dictionary_df[
                "_column_name_normalized"
            ] = (
                dictionary_df[
                    "column_name"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
            )

            dictionary_usage = _records(
                dictionary_df[
                    dictionary_df[
                        "_column_name_normalized"
                    ].isin(
                        wanted
                    )
                ].drop(
                    columns=[
                        "_column_name_normalized"
                    ]
                )
            )

    except Exception:
        dictionary_usage = []

    # --------------------------------------------------------
    # Return observed evidence
    # --------------------------------------------------------
    return {
        "column_names": sorted(
            wanted
        ),
        "column_usage": (
            column_usage[
                :max_records
            ]
        ),
        "primary_key_usage": (
            primary_key_usage[
                :max_records
            ]
        ),
        "foreign_key_usage": (
            foreign_key_usage[
                :max_records
            ]
        ),
        "dictionary_usage": (
            dictionary_usage[
                :max_records
            ]
        ),
    }

def inspect_table_evidence(
    target_engine,
    dictionary_engine,
    *,
    source_db,
    schema_name,
    table_name,
):
    """Collect the deterministic baseline evidence for one table in one call."""
    return {
        "target": {
            "source_db": source_db,
            "schema_name": schema_name,
            "table_name": table_name,
        },
        "columns": inspect_columns(
            target_engine,
            schema_name=schema_name,
            table_name=table_name,
        ),
        "primary_keys": inspect_primary_keys(
            target_engine,
            schema_name=schema_name,
            table_name=table_name,
        ),
        "foreign_keys": inspect_foreign_keys(
            target_engine,
            schema_name=schema_name,
            table_name=table_name,
        ),
        "indexes": inspect_indexes(
            target_engine,
            schema_name=schema_name,
            table_name=table_name,
        ),
        "unique_constraints": inspect_unique_constraints(
            target_engine,
            schema_name=schema_name,
            table_name=table_name,
        ),
        "table_dictionary": inspect_table_dictionary(
            dictionary_engine,
            source_db=source_db,
            schema_name=schema_name,
            table_name=table_name,
        ),
        "column_dictionary": inspect_column_dictionary(
            dictionary_engine,
            source_db=source_db,
            schema_name=schema_name,
            table_name=table_name,
        ),
    }


