"""Read-only access and deterministic context construction for NRI semantic dictionaries."""

import time

import pandas as pd
from sqlalchemy import text


def get_table_dictionary_record(
    engine,
    source_db: str,
    schema_name: str,
    table_name: str,
) -> dict:
    sql = """
    SELECT
        source_db,
        schema_name,
        table_name,
        business_name,
        business_purpose,
        subject_area,
        grain_description,
        business_key,
        refresh_frequency,
        owner_department,
        ai_description,
        verified
    FROM ai.table_dictionary
    WHERE source_db = :source_db
      AND schema_name = :schema_name
      AND table_name = :table_name
    LIMIT 1
    """

    try:
        df = pd.read_sql(
            text(sql),
            engine,
            params={
                "source_db": source_db,
                "schema_name": schema_name,
                "table_name": table_name,
            },
        )
    except Exception:
        return {}

    if df.empty:
        return {}

    return df.iloc[0].to_dict()

def get_column_dictionary_records(
    engine,
    source_db: str,
    schema_name: str,
    table_name: str,
) -> pd.DataFrame:
    sql = """
    SELECT
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
      AND schema_name = :schema_name
      AND table_name = :table_name
    ORDER BY column_name
    """

    try:
        return pd.read_sql(
            text(sql),
            engine,
            params={
                "source_db": source_db,
                "schema_name": schema_name,
                "table_name": table_name,
            },
        )
    except Exception:
        return pd.DataFrame()


def build_ai_data_dictionary_context(
    target_db: str,
    schema_name: str,
    table_name: str,
    physical_columns_df: pd.DataFrame,
    primary_keys_df: pd.DataFrame,
    outgoing_foreign_keys_df: pd.DataFrame,
    incoming_foreign_keys_df: pd.DataFrame,
    indexes_df: pd.DataFrame,
    table_dictionary: dict,
    column_dictionary_df: pd.DataFrame,
) -> dict:
    """
    Build factual context sent to the LLM.

    The LLM may interpret and enrich this information,
    but it may not add physical columns that do not exist.
    """

    physical_column_names = (
        physical_columns_df[
            "column_name"
        ]
        .dropna()
        .astype(str)
        .tolist()
        if not physical_columns_df.empty
        else []
    )

    return {
        "target_database": target_db,

        "generated_at": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "selected_table": {
            "schema_name": schema_name,
            "table_name": table_name,
            "full_name": (
                f"{schema_name}.{table_name}"
            ),
        },

        "generation_rules": {
            "physical_column_count": len(
                physical_column_names
            ),
            "required_physical_columns": (
                physical_column_names
            ),
            "one_output_item_per_physical_column": True,
            "extra_columns_allowed": False,
            "missing_columns_allowed": False,
        },

        "physical_columns": (
            physical_columns_df
            .fillna("")
            .to_dict(
                orient="records"
            )
            if not physical_columns_df.empty
            else []
        ),

        "primary_keys": (
            primary_keys_df
            .fillna("")
            .to_dict(
                orient="records"
            )
            if not primary_keys_df.empty
            else []
        ),

        "outgoing_foreign_keys": (
            outgoing_foreign_keys_df
            .fillna("")
            .to_dict(
                orient="records"
            )
            if not outgoing_foreign_keys_df.empty
            else []
        ),

        "incoming_foreign_keys": (
            incoming_foreign_keys_df
            .fillna("")
            .to_dict(
                orient="records"
            )
            if not incoming_foreign_keys_df.empty
            else []
        ),

        "indexes": (
            indexes_df
            .fillna("")
            .to_dict(
                orient="records"
            )
            if not indexes_df.empty
            else []
        ),

        "existing_table_dictionary": (
            table_dictionary
            if table_dictionary
            else {}
        ),

        "existing_column_dictionary": (
            column_dictionary_df
            .fillna("")
            .to_dict(
                orient="records"
            )
            if not column_dictionary_df.empty
            else []
        ),
    }
