"""Business Consistency analysis for NRI DBA workflows.

Contains deterministic DBA-domain data preparation and evidence/context
construction. Streamlit UI and PDF rendering remain outside this module.
"""

import time

import pandas as pd
from sqlalchemy import text

def normalize_postgres_data_type(
    data_type: str,
    udt_name: str = "",
) -> str:
    """
    Normalize PostgreSQL data types for relationship comparison.

    Examples:
    - int4 -> integer
    - int8 -> bigint
    - varchar -> character varying
    - timestamptz -> timestamp with time zone
    """

    data_type = str(
        data_type or ""
    ).strip().lower()

    udt_name = str(
        udt_name or ""
    ).strip().lower()

    aliases = {
        "int2": "smallint",
        "int4": "integer",
        "int8": "bigint",
        "float4": "real",
        "float8": "double precision",
        "bool": "boolean",
        "varchar": "character varying",
        "bpchar": "character",
        "timestamptz": "timestamp with time zone",
        "timestamp": "timestamp without time zone",
        "date": "date",
        "numeric": "numeric",
        "text": "text",
        "uuid": "uuid",
    }

    if udt_name in aliases:
        return aliases[udt_name]

    if data_type in aliases:
        return aliases[data_type]

    return data_type

def build_column_usage_review(
    all_columns_df,
    primary_keys_df,
    foreign_keys_df,
    column_name,
):
    usage_df = all_columns_df[
        all_columns_df[
            "column_name"
        ] == column_name
    ].copy()

    pk_keys = set(
        zip(
            primary_keys_df[
                "table_schema"
            ],
            primary_keys_df[
                "table_name"
            ],
            primary_keys_df[
                "column_name"
            ],
        )
    )

    fk_keys = set(
        zip(
            foreign_keys_df[
                "source_schema"
            ],
            foreign_keys_df[
                "source_table"
            ],
            foreign_keys_df[
                "source_column"
            ],
        )
    )

    usage_df[
        "is_primary_key"
    ] = usage_df.apply(
        lambda row: (
            row["table_schema"],
            row["table_name"],
            row["column_name"],
        ) in pk_keys,
        axis=1,
    )

    usage_df[
        "is_foreign_key"
    ] = usage_df.apply(
        lambda row: (
            row["table_schema"],
            row["table_name"],
            row["column_name"],
        ) in fk_keys,
        axis=1,
    )

    return usage_df

def get_business_consistency_dictionary_context(
    control_engine,
    source_db: str,
    column_name: str,
) -> pd.DataFrame:
    """
    Load table-level and column-level business dictionary
    information for every table using the selected column.
    """

    sql = """
    SELECT
        dd.schema_name AS table_schema,
        dd.table_name,
        dd.column_name,
        td.business_name AS table_business_name,
        td.business_purpose,
        td.subject_area,
        td.grain_description,
        td.business_key,
        td.owner_department,
        td.verified AS table_dictionary_verified,
        dd.business_name AS column_business_name,
        dd.description AS column_business_description,
        dd.data_role,
        dd.semantic_type,
        dd.allowed_values,
        dd.example_values,
        dd.join_hint,
        dd.filter_hint,
        dd.aggregation_hint,
        dd.is_primary_key AS dictionary_is_primary_key,
        dd.is_foreign_key AS dictionary_is_foreign_key,
        dd.verified AS column_dictionary_verified
    FROM ai.data_dictionary dd
    LEFT JOIN ai.table_dictionary td
      ON td.source_db = dd.source_db
     AND td.schema_name = dd.schema_name
     AND td.table_name = dd.table_name
    WHERE dd.source_db = :source_db
      AND dd.column_name = :column_name
    ORDER BY
        dd.schema_name,
        dd.table_name
    """
    try:
        return pd.read_sql(
            text(sql),
            control_engine,
            params={
                "source_db": source_db,
                "column_name": column_name,
            },
        )
    except Exception:
        return pd.DataFrame()

def build_business_consistency_usage_context(
    usage_df: pd.DataFrame,
    dictionary_context_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge physical PostgreSQL metadata with table-level
    and column-level business dictionary information.
    """
    result_df = usage_df.copy()
    if not dictionary_context_df.empty:
        result_df = result_df.merge(
            dictionary_context_df,
            on=[
                "table_schema",
                "table_name",
                "column_name",
            ],
            how="left",
        )
    text_columns = [
        "table_business_name",
        "business_purpose",
        "subject_area",
        "grain_description",
        "business_key",
        "owner_department",
        "column_business_name",
        "column_business_description",
        "data_role",
        "semantic_type",
        "allowed_values",
        "example_values",
        "join_hint",
        "filter_hint",
        "aggregation_hint",
    ]

    for column in text_columns:
        if column not in result_df.columns:
            result_df[column] = ""
        else:
            result_df[column] = (
                result_df[column]
                .fillna("")
                .astype(str)
            )
    boolean_columns = [
        "table_dictionary_verified",
        "column_dictionary_verified",
        "dictionary_is_primary_key",
        "dictionary_is_foreign_key",
    ]

    for column in boolean_columns:
        if column not in result_df.columns:
            result_df[column] = False
        else:
            result_df[column] = (
                result_df[column]
                .fillna(False)
                .astype(bool)
            )

    return result_df

def build_business_consistency_report_context(
    target_db: str,
    selected_column: str,
    usage_context_df: pd.DataFrame,
) -> dict:
    """
    Build factual JSON context for the Business Consistency report.
    """
    if usage_context_df.empty:
        table_count = 0
        pk_usage_count = 0
        fk_usage_count = 0
        type_count = 0
        table_dictionary_count = 0
        column_dictionary_count = 0
    else:
        table_count = int(
            usage_context_df[
                [
                    "table_schema",
                    "table_name",
                ]
            ]
            .drop_duplicates()
            .shape[0]
        )
        pk_usage_count = int(
            usage_context_df[
                "is_primary_key"
            ]
            .fillna(False)
            .astype(bool)
            .sum()
        )
        fk_usage_count = int(
            usage_context_df[
                "is_foreign_key"
            ]
            .fillna(False)
            .astype(bool)
            .sum()
        )
        normalized_types = usage_context_df.apply(
            lambda row: normalize_postgres_data_type(
                row.get(
                    "data_type",
                    "",
                ),
                row.get(
                    "udt_name",
                    "",
                ),
            ),
            axis=1,
        )
        type_count = int(
            normalized_types.nunique()
        )

        table_dictionary_count = int(
            (
             usage_context_df[
                    "table_business_name"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                != ""
            ).sum()
        )
        column_dictionary_count = int(
            (
                usage_context_df[
                    "column_business_name"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                != ""
            ).sum()
        )

    return {
        "target_database": target_db,
        "selected_column": selected_column,
        "generated_at": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "inventory_summary": {
            "table_count": table_count,
            "primary_key_usage_count": (
                pk_usage_count
            ),
            "foreign_key_usage_count": (
                fk_usage_count
            ),
            "distinct_data_type_count": (
                type_count
            ),
            "table_business_name_count": (
                table_dictionary_count
            ),
            "column_business_name_count": (
                column_dictionary_count
            ),
        },
        "column_usage": (
            usage_context_df
            .fillna("")
            .to_dict(
                orient="records"
            )
        ),
    }

