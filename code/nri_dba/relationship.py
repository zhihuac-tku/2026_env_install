 # py code beginning

"""Deterministic DBA relationship analysis helpers.

This module contains read-only relationship analysis logic used by
nri_dba.evidence.

It does not contain Agent, LLM, Streamlit, or database runtime code.
"""

from typing import Any

import pandas as pd


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _first_existing_column(
    df: pd.DataFrame,
    candidates: tuple[str, ...],
) -> str | None:
    """Return the first candidate column that exists in the DataFrame."""
    if df is None or df.empty:
        return None

    for name in candidates:
        if name in df.columns:
            return name

    return None


def _safe_text(value: Any) -> str:
    """Convert metadata values to clean strings."""
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip()


def _normalize_name(value: Any) -> str:
    """Normalize an identifier for comparison."""
    return _safe_text(value).lower()


def _table_identity(
    row: pd.Series,
) -> tuple[str, str]:
    """Extract schema/table identity from a metadata row."""

    schema_name = ""

    for key in (
        "schema_name",
        "table_schema",
        "source_schema",
        "foreign_schema_name",
        "referenced_schema",
        "target_schema",
    ):
        if key in row.index:
            value = _safe_text(row.get(key))
            if value:
                schema_name = value
                break

    table_name = ""

    for key in (
        "table_name",
        "source_table",
        "foreign_table_name",
        "referenced_table",
        "target_table",
    ):
        if key in row.index:
            value = _safe_text(row.get(key))
            if value:
                table_name = value
                break

    return schema_name, table_name


def _column_identity(
    row: pd.Series,
) -> str:
    """Extract a column name from a metadata row."""

    for key in (
        "column_name",
        "source_column",
        "foreign_column_name",
        "referenced_column",
        "target_column",
    ):
        if key in row.index:
            value = _safe_text(row.get(key))
            if value:
                return value

    return ""


def _empty_candidate_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "source_schema",
            "source_table",
            "source_column",
            "target_schema",
            "target_table",
            "target_column",
            "relationship_type",
            "confidence",
            "reason",
        ]
    )


# ============================================================
# 1. CANDIDATE RELATIONSHIPS
# ============================================================

def build_candidate_relationships_for_table(
    all_columns: pd.DataFrame,
    primary_keys: pd.DataFrame,
    foreign_keys: pd.DataFrame,
    schema_name: str,
    table_name: str,
) -> pd.DataFrame:
    """Build logical relationship candidates for one target table.

    Candidate relationships are inferred from repeated column names and
    primary-key evidence.

    They are analytical candidates only. They must not be interpreted as
    physical foreign-key constraints.
    """

    if all_columns is None or all_columns.empty:
        return _empty_candidate_frame()

    target_schema = _normalize_name(schema_name)
    target_table = _normalize_name(table_name)

    # --------------------------------------------------------
    # Normalize physical FK evidence so inferred candidates
    # that are already represented by a real FK can be skipped.
    # --------------------------------------------------------

    physical_fk_pairs: set[
        tuple[str, str, str, str, str, str]
    ] = set()

    if foreign_keys is not None and not foreign_keys.empty:
        for _, row in foreign_keys.iterrows():

            source_schema = _safe_text(
                row.get(
                    "source_schema",
                    row.get(
                        "schema_name",
                        row.get(
                            "foreign_schema_name",
                            "",
                        ),
                    ),
                )
            )

            source_table = _safe_text(
                row.get(
                    "source_table",
                    row.get(
                        "table_name",
                        row.get(
                            "foreign_table_name",
                            "",
                        ),
                    ),
                )
            )

            source_column = _safe_text(
                row.get(
                    "source_column",
                    row.get(
                        "column_name",
                        row.get(
                            "foreign_column_name",
                            "",
                        ),
                    ),
                )
            )

            referenced_schema = _safe_text(
                row.get(
                    "target_schema",
                    row.get(
                        "referenced_schema",
                        "",
                    ),
                )
            )

            referenced_table = _safe_text(
                row.get(
                    "target_table",
                    row.get(
                        "referenced_table",
                        "",
                    ),
                )
            )

            referenced_column = _safe_text(
                row.get(
                    "target_column",
                    row.get(
                        "referenced_column",
                        "",
                    ),
                )
            )

            physical_fk_pairs.add(
                (
                    _normalize_name(source_schema),
                    _normalize_name(source_table),
                    _normalize_name(source_column),
                    _normalize_name(referenced_schema),
                    _normalize_name(referenced_table),
                    _normalize_name(referenced_column),
                )
            )

    # --------------------------------------------------------
    # Build PK lookup
    # --------------------------------------------------------

    pk_lookup: set[tuple[str, str, str]] = set()

    if primary_keys is not None and not primary_keys.empty:
        for _, row in primary_keys.iterrows():
            pk_schema, pk_table = _table_identity(row)
            pk_column = _column_identity(row)

            if pk_table and pk_column:
                pk_lookup.add(
                    (
                        _normalize_name(pk_schema),
                        _normalize_name(pk_table),
                        _normalize_name(pk_column),
                    )
                )

    # --------------------------------------------------------
    # Identify target-table columns
    # --------------------------------------------------------

    target_rows: list[pd.Series] = []

    for _, row in all_columns.iterrows():
        row_schema, row_table = _table_identity(row)

        if (
            _normalize_name(row_table) == target_table
            and (
                not target_schema
                or not row_schema
                or _normalize_name(row_schema) == target_schema
            )
        ):
            target_rows.append(row)

    # all_columns may have been pre-filtered by evidence.py.
    # If the target rows are not present, no safe target-side
    # relationship inference can be made.
    if not target_rows:
        return _empty_candidate_frame()

    results: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()

    # --------------------------------------------------------
    # Same-name relationship inference
    # --------------------------------------------------------

    for target_row in target_rows:

        source_schema, source_table = _table_identity(
            target_row
        )
        source_column = _column_identity(target_row)

        if not source_column:
            continue

        normalized_column = _normalize_name(source_column)

        for _, candidate_row in all_columns.iterrows():

            candidate_schema, candidate_table = (
                _table_identity(candidate_row)
            )
            candidate_column = _column_identity(
                candidate_row
            )

            if not candidate_table or not candidate_column:
                continue

            # Do not relate a table to itself.
            if (
                _normalize_name(candidate_schema)
                == _normalize_name(source_schema)
                and _normalize_name(candidate_table)
                == _normalize_name(source_table)
            ):
                continue

            if (
                _normalize_name(candidate_column)
                != normalized_column
            ):
                continue

            target_is_pk = (
                _normalize_name(candidate_schema),
                _normalize_name(candidate_table),
                _normalize_name(candidate_column),
            ) in pk_lookup

            source_is_pk = (
                _normalize_name(source_schema),
                _normalize_name(source_table),
                normalized_column,
            ) in pk_lookup

            relationship_type = (
                "same_name_primary_key_candidate"
                if target_is_pk or source_is_pk
                else "same_name_column_candidate"
            )

            confidence = (
                "high"
                if target_is_pk
                else "medium"
                if source_is_pk
                else "low"
            )

            if target_is_pk:
                reason = (
                    f"{source_column} also appears as a "
                    f"primary-key column in "
                    f"{candidate_schema}.{candidate_table}."
                )
            elif source_is_pk:
                reason = (
                    f"{source_column} is a primary-key column "
                    f"in the selected table and also appears "
                    f"in {candidate_schema}.{candidate_table}."
                )
            else:
                reason = (
                    f"Column name {source_column} appears in "
                    f"both tables."
                )

            physical_key = (
                _normalize_name(source_schema),
                _normalize_name(source_table),
                normalized_column,
                _normalize_name(candidate_schema),
                _normalize_name(candidate_table),
                _normalize_name(candidate_column),
            )

            reverse_physical_key = (
                _normalize_name(candidate_schema),
                _normalize_name(candidate_table),
                _normalize_name(candidate_column),
                _normalize_name(source_schema),
                _normalize_name(source_table),
                normalized_column,
            )

            # Already represented by a physical FK.
            if (
                physical_key in physical_fk_pairs
                or reverse_physical_key in physical_fk_pairs
            ):
                continue

            dedupe_key = (
                _normalize_name(source_schema),
                _normalize_name(source_table),
                normalized_column,
                _normalize_name(candidate_schema),
                _normalize_name(candidate_table),
                _normalize_name(candidate_column),
            )

            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)

            results.append(
                {
                    "source_schema": source_schema,
                    "source_table": source_table,
                    "source_column": source_column,
                    "target_schema": candidate_schema,
                    "target_table": candidate_table,
                    "target_column": candidate_column,
                    "relationship_type": relationship_type,
                    "confidence": confidence,
                    "reason": reason,
                }
            )

    if not results:
        return _empty_candidate_frame()

    return pd.DataFrame(results)


# ============================================================
# 2. RELATIONSHIP COLUMN USAGE
# ============================================================

def build_relationship_column_usage(
    all_columns: pd.DataFrame,
    selected_columns: pd.DataFrame,
) -> pd.DataFrame:
    """Find where selected relationship columns occur.

    `selected_columns` should contain the small set of columns selected by
    the Investigator Agent for relationship drill-down.
    """

    output_columns = [
        "selected_column",
        "schema_name",
        "table_name",
        "column_name",
        "data_type",
        "ordinal_position",
    ]

    if (
        all_columns is None
        or all_columns.empty
        or selected_columns is None
        or selected_columns.empty
    ):
        return pd.DataFrame(columns=output_columns)

    selected_names: set[str] = set()

    for _, row in selected_columns.iterrows():
        name = _column_identity(row)

        if name:
            selected_names.add(
                _normalize_name(name)
            )

    if not selected_names:
        return pd.DataFrame(columns=output_columns)

    results: list[dict[str, Any]] = []

    for _, row in all_columns.iterrows():

        column_name = _column_identity(row)

        if (
            not column_name
            or _normalize_name(column_name)
            not in selected_names
        ):
            continue

        schema_name, table_name = _table_identity(row)

        data_type = ""

        for key in (
            "data_type",
            "udt_name",
            "column_type",
        ):
            if key in row.index:
                value = _safe_text(row.get(key))
                if value:
                    data_type = value
                    break

        ordinal_position = None

        if "ordinal_position" in row.index:
            value = row.get("ordinal_position")

            try:
                if not pd.isna(value):
                    ordinal_position = value
            except (TypeError, ValueError):
                ordinal_position = value

        results.append(
            {
                "selected_column": column_name,
                "schema_name": schema_name,
                "table_name": table_name,
                "column_name": column_name,
                "data_type": data_type,
                "ordinal_position": ordinal_position,
            }
        )

    if not results:
        return pd.DataFrame(columns=output_columns)

    result_df = pd.DataFrame(results)

    available_sort_columns = [
        column
        for column in (
            "selected_column",
            "schema_name",
            "table_name",
            "ordinal_position",
        )
        if column in result_df.columns
    ]

    if available_sort_columns:
        result_df = result_df.sort_values(
            available_sort_columns,
            kind="stable",
        )

    return result_df.reset_index(drop=True)


# ============================================================
# 3. RELATIONSHIP IMPACT SUMMARY
# ============================================================

def build_relationship_impact_summary(
    incoming_foreign_keys: pd.DataFrame,
    outgoing_foreign_keys: pd.DataFrame,
    candidates: pd.DataFrame,
) -> dict[str, Any]:
    """Build a deterministic summary of relationship evidence."""

    incoming_count = (
        0
        if incoming_foreign_keys is None
        else len(incoming_foreign_keys)
    )

    outgoing_count = (
        0
        if outgoing_foreign_keys is None
        else len(outgoing_foreign_keys)
    )

    candidate_count = (
        0
        if candidates is None
        else len(candidates)
    )

    physical_relationship_count = (
        incoming_count + outgoing_count
    )

    has_physical_relationships = (
        physical_relationship_count > 0
    )

    has_candidate_relationships = (
        candidate_count > 0
    )

    if has_physical_relationships:
        relationship_status = (
            "physical_relationships_present"
        )
    elif has_candidate_relationships:
        relationship_status = (
            "candidate_relationships_only"
        )
    else:
        relationship_status = (
            "no_relationship_evidence"
        )

    if incoming_count > 0 and outgoing_count > 0:
        impact_level = "high"
    elif physical_relationship_count > 0:
        impact_level = "medium"
    elif candidate_count > 0:
        impact_level = "potential"
    else:
        impact_level = "none"

    return {
        "incoming_foreign_key_count": incoming_count,
        "outgoing_foreign_key_count": outgoing_count,
        "physical_relationship_count": (
            physical_relationship_count
        ),
        "candidate_relationship_count": candidate_count,
        "has_physical_relationships": (
            has_physical_relationships
        ),
        "has_candidate_relationships": (
            has_candidate_relationships
        ),
        "relationship_status": relationship_status,
        "impact_level": impact_level,
        "requires_human_review": (
            has_candidate_relationships
        ),
    }

# ============================================================
# 4. SIMILAR TABLE DISCOVERY
# ============================================================

def find_similar_tables(
    proposed_columns: pd.DataFrame,
    all_columns: pd.DataFrame,
    primary_keys: pd.DataFrame | None = None,
    table_dictionary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Find existing tables similar to a proposed table design.

    Similarity is based on deterministic metadata evidence:

    - proposed-column coverage
    - existing-table coverage
    - Jaccard column similarity
    - matching data types
    - existing primary-key columns
    - optional table-dictionary context

    The result is evidence only. Similarity does not prove that two
    tables have the same business purpose or grain.
    """

    output_columns = [
        "table_schema",
        "table_name",
        "full_table_name",
        "uploaded_column_count",
        "existing_column_count",
        "matched_column_count",
        "matched_columns",
        "upload_coverage",
        "existing_coverage",
        "jaccard_similarity",
        "type_match_rate",
        "primary_key_columns",
        "business_name",
        "business_purpose",
        "grain_description",
    ]

    if (
        proposed_columns is None
        or proposed_columns.empty
        or all_columns is None
        or all_columns.empty
    ):
        return pd.DataFrame(
            columns=output_columns
        )

    if "column_name" not in proposed_columns.columns:
        return pd.DataFrame(
            columns=output_columns
        )

    if (
        "table_name" not in all_columns.columns
        or "column_name" not in all_columns.columns
    ):
        return pd.DataFrame(
            columns=output_columns
        )

    # --------------------------------------------------------
    # Proposed columns
    # --------------------------------------------------------

    proposed_column_set = {
        _normalize_name(value)
        for value
        in proposed_columns[
            "column_name"
        ].tolist()
        if _safe_text(value)
    }

    if not proposed_column_set:
        return pd.DataFrame(
            columns=output_columns
        )

    # --------------------------------------------------------
    # Proposed data types
    # --------------------------------------------------------

    proposed_type_map: dict[str, str] = {}

    if "data_type" in proposed_columns.columns:

        for _, row in proposed_columns.iterrows():

            column_name = _normalize_name(
                row.get(
                    "column_name",
                    "",
                )
            )

            if not column_name:
                continue

            proposed_type_map[
                column_name
            ] = _normalize_name(
                row.get(
                    "data_type",
                    "",
                )
            )

    # --------------------------------------------------------
    # Existing PK lookup
    # --------------------------------------------------------

    pk_lookup: dict[
        tuple[str, str],
        list[str],
    ] = {}

    if (
        primary_keys is not None
        and not primary_keys.empty
    ):

        for _, row in primary_keys.iterrows():

            schema_name, table_name = (
                _table_identity(row)
            )

            column_name = (
                _column_identity(row)
            )

            if (
                not table_name
                or not column_name
            ):
                continue

            key = (
                _normalize_name(
                    schema_name
                ),
                _normalize_name(
                    table_name
                ),
            )

            pk_lookup.setdefault(
                key,
                [],
            ).append(
                column_name
            )

    # --------------------------------------------------------
    # Optional table dictionary lookup
    # --------------------------------------------------------

    table_dictionary_lookup: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    if (
        table_dictionary is not None
        and not table_dictionary.empty
    ):

        for _, row in table_dictionary.iterrows():

            schema_name = _safe_text(
                row.get(
                    "schema_name",
                    row.get(
                        "table_schema",
                        "",
                    ),
                )
            )

            table_name = _safe_text(
                row.get(
                    "table_name",
                    "",
                )
            )

            if not table_name:
                continue

            key = (
                _normalize_name(
                    schema_name
                ),
                _normalize_name(
                    table_name
                ),
            )

            table_dictionary_lookup[
                key
            ] = row.to_dict()

    # --------------------------------------------------------
    # Existing schema-column names
    # --------------------------------------------------------

    schema_column = _first_existing_column(
        all_columns,
        (
            "table_schema",
            "schema_name",
        ),
    )

    if schema_column is None:
        working_columns = (
            all_columns.copy()
        )

        working_columns[
            "_relationship_schema"
        ] = ""

        schema_column = (
            "_relationship_schema"
        )

    else:
        working_columns = (
            all_columns.copy()
        )

    # --------------------------------------------------------
    # Compare proposed table with every existing table
    # --------------------------------------------------------

    results: list[
        dict[str, Any]
    ] = []

    table_groups = (
        working_columns.groupby(
            [
                schema_column,
                "table_name",
            ],
            dropna=False,
        )
    )

    for (
        existing_schema,
        existing_table,
    ), table_columns in table_groups:

        existing_schema = _safe_text(
            existing_schema
        )

        existing_table = _safe_text(
            existing_table
        )

        if not existing_table:
            continue

        existing_column_set = {
            _normalize_name(value)
            for value
            in table_columns[
                "column_name"
            ].tolist()
            if _safe_text(value)
        }

        if not existing_column_set:
            continue

        matched_columns = (
            proposed_column_set
            & existing_column_set
        )

        union_columns = (
            proposed_column_set
            | existing_column_set
        )

        upload_coverage = (
            len(matched_columns)
            / max(
                len(
                    proposed_column_set
                ),
                1,
            )
        )

        existing_coverage = (
            len(matched_columns)
            / max(
                len(
                    existing_column_set
                ),
                1,
            )
        )

        jaccard_similarity = (
            len(matched_columns)
            / max(
                len(
                    union_columns
                ),
                1,
            )
        )

        # ----------------------------------------------------
        # Type match rate
        # ----------------------------------------------------

        matched_type_count = 0

        for matched_column in matched_columns:

            existing_rows = (
                table_columns[
                    table_columns[
                        "column_name"
                    ]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    == matched_column
                ]
            )

            if existing_rows.empty:
                continue

            existing_row = (
                existing_rows.iloc[0]
            )

            existing_type = _normalize_name(
                existing_row.get(
                    "data_type",
                    existing_row.get(
                        "udt_name",
                        "",
                    ),
                )
            )

            proposed_type = (
                proposed_type_map.get(
                    matched_column,
                    "",
                )
            )

            if (
                existing_type
                and proposed_type
                and existing_type
                == proposed_type
            ):
                matched_type_count += 1

        type_match_rate = (
            matched_type_count
            / max(
                len(
                    matched_columns
                ),
                1,
            )
            if matched_columns
            else 0.0
        )

        # ----------------------------------------------------
        # PK evidence
        # ----------------------------------------------------

        table_key = (
            _normalize_name(
                existing_schema
            ),
            _normalize_name(
                existing_table
            ),
        )

        primary_key_columns = (
            pk_lookup.get(
                table_key,
                [],
            )
        )

        # ----------------------------------------------------
        # Dictionary evidence
        # ----------------------------------------------------

        dictionary_row = (
            table_dictionary_lookup.get(
                table_key,
                {},
            )
        )

        results.append(
            {
                "table_schema": (
                    existing_schema
                ),
                "table_name": (
                    existing_table
                ),
                "full_table_name": (
                    f"{existing_schema}."
                    f"{existing_table}"
                    if existing_schema
                    else existing_table
                ),
                "uploaded_column_count": (
                    len(
                        proposed_column_set
                    )
                ),
                "existing_column_count": (
                    len(
                        existing_column_set
                    )
                ),
                "matched_column_count": (
                    len(
                        matched_columns
                    )
                ),
                "matched_columns": (
                    ", ".join(
                        sorted(
                            matched_columns
                        )
                    )
                ),
                "upload_coverage": round(
                    upload_coverage,
                    3,
                ),
                "existing_coverage": round(
                    existing_coverage,
                    3,
                ),
                "jaccard_similarity": round(
                    jaccard_similarity,
                    3,
                ),
                "type_match_rate": round(
                    type_match_rate,
                    3,
                ),
                "primary_key_columns": (
                    ", ".join(
                        primary_key_columns
                    )
                ),
                "business_name": (
                    _safe_text(
                        dictionary_row.get(
                            "business_name",
                            "",
                        )
                    )
                ),
                "business_purpose": (
                    _safe_text(
                        dictionary_row.get(
                            "business_purpose",
                            "",
                        )
                    )
                ),
                "grain_description": (
                    _safe_text(
                        dictionary_row.get(
                            "grain_description",
                            "",
                        )
                    )
                ),
            }
        )

    if not results:
        return pd.DataFrame(
            columns=output_columns
        )

    result_df = pd.DataFrame(
        results
    )

    result_df = (
        result_df.sort_values(
            [
                "upload_coverage",
                "type_match_rate",
                "jaccard_similarity",
                "table_schema",
                "table_name",
            ],
            ascending=[
                False,
                False,
                False,
                True,
                True,
            ],
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )

    return result_df[
        output_columns
    ]

