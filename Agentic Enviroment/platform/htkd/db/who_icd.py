 # py code beginning

"""
WHO ICD query capability for HTKD.

Purpose
-------
Provide read-only access to WHO ICD Foundation and ICD-11 MMS
data stored in the HTKD PostgreSQL database.

This module does NOT:
- create database engines
- configure database connections
- perform clinical diagnosis
- decide the correct ICD code
- translate clinical text
- call an LLM

The SQLAlchemy engine must be supplied by the caller.

Typical architecture:

    nri_code_core.db.db_runtime
                |
                | engine
                v
        htkd.db.who_icd
                |
                | WHO ICD evidence
                v
        Clinical Review Agent
"""


from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


# ============================================================
# Constants
# ============================================================

DEFAULT_LANGUAGE = "en"
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50


FOUNDATION_SEARCH_TEXT_TYPES = (
    "title",
    "fullySpecifiedName",
    "synonym",
)


FOUNDATION_TEXT_TYPES = (
    "title",
    "fullySpecifiedName",
    "synonym",
    "definition",
    "longDefinition",
    "inclusion",
    "exclusion",
)


MMS_TEXT_TYPES = (
    "title",
    "definition",
    "longDefinition",
)


# ============================================================
# Internal Helpers
# ============================================================

def _normalize_query(
    query: str,
) -> str:
    """
    Normalize a user/tool supplied search query.

    This intentionally performs only minimal normalization.
    Clinical interpretation and translation belong outside
    this database capability.
    """

    return " ".join(
        str(query or "").strip().split()
    )


def _normalize_limit(
    limit: int,
) -> int:
    """
    Keep query limits within a safe range.
    """

    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = DEFAULT_SEARCH_LIMIT

    return max(
        1,
        min(
            value,
            MAX_SEARCH_LIMIT,
        ),
    )


def _rows_to_dicts(
    result,
) -> list[dict[str, Any]]:
    """
    Convert SQLAlchemy mapping rows into plain dictionaries.
    """

    return [
        dict(row)
        for row in result.mappings().all()
    ]


def _group_text_rows(
    rows: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """
    Group WHO text rows by text_type.

    Example:

        {
            "title": [
                "Diabetes mellitus"
            ],
            "definition": [
                "..."
            ],
            "synonym": [
                "...",
                "..."
            ]
        }
    """

    grouped: dict[str, list[str]] = {}

    for row in rows:
        text_type = str(
            row.get("text_type") or ""
        ).strip()

        text_value = str(
            row.get("text_value") or ""
        ).strip()

        if not text_type or not text_value:
            continue

        grouped.setdefault(
            text_type,
            [],
        )

        if text_value not in grouped[text_type]:
            grouped[text_type].append(
                text_value
            )

    return grouped


def _first_text(
    grouped_text: dict[str, list[str]],
    text_type: str,
) -> str | None:
    """
    Return the first text value for a text type.
    """

    values = grouped_text.get(
        text_type,
        [],
    )

    if not values:
        return None

    return values[0]


# ============================================================
# 1. Search WHO Foundation
# ============================================================

def search_foundation(
    *,
    engine: Engine,
    query: str,
    language: str = DEFAULT_LANGUAGE,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """
    Search WHO ICD Foundation concepts.

    Search fields:
    - title
    - fullySpecifiedName
    - synonym

    Ranking:
    1. exact title
    2. exact fullySpecifiedName
    3. exact synonym
    4. title starts with query
    5. fullySpecifiedName starts with query
    6. synonym starts with query
    7. title contains query
    8. fullySpecifiedName contains query
    9. synonym contains query

    This function returns candidate concepts only.

    It does NOT determine which candidate is clinically correct.
    """

    query = _normalize_query(
        query
    )

    if not query:
        return []

    language = (
        str(language or DEFAULT_LANGUAGE)
        .strip()
    )

    limit = _normalize_limit(
        limit
    )

    sql = text(
        """
        WITH ranked_matches AS (
            SELECT
                e.who_icd_entity_id,
                e.dataset_version_id,
                e.foundation_uri,
                e.browser_url,

                t.language_code,
                t.text_type,
                t.text_value,

                CASE
                    WHEN
                        t.text_type = 'title'
                        AND lower(t.text_value) = lower(:query)
                    THEN 1

                    WHEN
                        t.text_type = 'fullySpecifiedName'
                        AND lower(t.text_value) = lower(:query)
                    THEN 2

                    WHEN
                        t.text_type = 'synonym'
                        AND lower(t.text_value) = lower(:query)
                    THEN 3

                    WHEN
                        t.text_type = 'title'
                        AND lower(t.text_value)
                            LIKE lower(:query) || '%%'
                    THEN 4

                    WHEN
                        t.text_type = 'fullySpecifiedName'
                        AND lower(t.text_value)
                            LIKE lower(:query) || '%%'
                    THEN 5

                    WHEN
                        t.text_type = 'synonym'
                        AND lower(t.text_value)
                            LIKE lower(:query) || '%%'
                    THEN 6

                    WHEN
                        t.text_type = 'title'
                    THEN 7

                    WHEN
                        t.text_type = 'fullySpecifiedName'
                    THEN 8

                    WHEN
                        t.text_type = 'synonym'
                    THEN 9

                    ELSE 10
                END AS match_rank

            FROM terminology.who_icd_entity e

            JOIN terminology.who_icd_entity_text t
                ON t.who_icd_entity_id =
                   e.who_icd_entity_id

            WHERE
                t.language_code = :language

                AND t.text_type IN (
                    'title',
                    'fullySpecifiedName',
                    'synonym'
                )

                AND lower(t.text_value)
                    LIKE '%%' || lower(:query) || '%%'
        ),

        best_entity_matches AS (
            SELECT DISTINCT ON (
                who_icd_entity_id
            )
                who_icd_entity_id,
                dataset_version_id,
                foundation_uri,
                browser_url,
                language_code,
                text_type,
                text_value,
                match_rank

            FROM ranked_matches

            ORDER BY
                who_icd_entity_id,
                match_rank,
                length(text_value),
                text_value
        )

        SELECT
            who_icd_entity_id,
            dataset_version_id,
            foundation_uri,
            browser_url,
            language_code,
            text_type AS matched_text_type,
            text_value AS matched_text,
            match_rank

        FROM best_entity_matches

        ORDER BY
            match_rank,
            length(text_value),
            text_value

        LIMIT :limit
        """
    )

    with engine.connect() as conn:
        result = conn.execute(
            sql,
            {
                "query": query,
                "language": language,
                "limit": limit,
            },
        )

        return _rows_to_dicts(
            result
        )


# ============================================================
# 2. Get WHO Foundation Entity
# ============================================================

def get_foundation_entity(
    *,
    engine: Engine,
    foundation_uri: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, Any] | None:
    """
    Retrieve one WHO ICD Foundation entity together with
    its available human-readable text.

    Possible Foundation text types currently observed in HTKD:

    - title
    - fullySpecifiedName
    - synonym
    - definition
    - longDefinition
    - inclusion
    - exclusion
    """

    foundation_uri = str(
        foundation_uri or ""
    ).strip()

    if not foundation_uri:
        return None

    language = (
        str(language or DEFAULT_LANGUAGE)
        .strip()
    )

    entity_sql = text(
        """
        SELECT
            e.who_icd_entity_id,
            e.dataset_version_id,
            e.foundation_uri,
            e.browser_url,
            e.created_at

        FROM terminology.who_icd_entity e

        WHERE
            e.foundation_uri = :foundation_uri

        ORDER BY
            e.dataset_version_id DESC

        LIMIT 1
        """
    )

    with engine.connect() as conn:

        entity_result = conn.execute(
            entity_sql,
            {
                "foundation_uri":
                    foundation_uri,
            },
        ).mappings().first()

        if entity_result is None:
            return None

        entity = dict(
            entity_result
        )

        text_sql = text(
            """
            SELECT
                t.language_code,
                t.text_type,
                t.text_value

            FROM terminology.who_icd_entity_text t

            WHERE
                t.who_icd_entity_id =
                    :who_icd_entity_id

                AND t.language_code =
                    :language

            ORDER BY
                CASE t.text_type
                    WHEN 'title' THEN 1
                    WHEN 'fullySpecifiedName' THEN 2
                    WHEN 'synonym' THEN 3
                    WHEN 'definition' THEN 4
                    WHEN 'longDefinition' THEN 5
                    WHEN 'inclusion' THEN 6
                    WHEN 'exclusion' THEN 7
                    ELSE 8
                END,
                t.text_value
            """
        )

        text_result = conn.execute(
            text_sql,
            {
                "who_icd_entity_id":
                    entity["who_icd_entity_id"],
                "language":
                    language,
            },
        )

        text_rows = _rows_to_dicts(
            text_result
        )

    grouped_text = _group_text_rows(
        text_rows
    )

    return {
        **entity,

        "language_code":
            language,

        "title":
            _first_text(
                grouped_text,
                "title",
            ),

        "fully_specified_name":
            _first_text(
                grouped_text,
                "fullySpecifiedName",
            ),

        "synonyms":
            grouped_text.get(
                "synonym",
                [],
            ),

        "definitions":
            grouped_text.get(
                "definition",
                [],
            ),

        "long_definitions":
            grouped_text.get(
                "longDefinition",
                [],
            ),

        "inclusions":
            grouped_text.get(
                "inclusion",
                [],
            ),

        "exclusions":
            grouped_text.get(
                "exclusion",
                [],
            ),

        "text":
            grouped_text,
    }


# ============================================================
# 3. Get MMS Entity for Foundation Concept
# ============================================================

def get_mms_for_foundation(
    *,
    engine: Engine,
    foundation_uri: str,
    language: str = DEFAULT_LANGUAGE,
) -> list[dict[str, Any]]:
    """
    Retrieve ICD-11 MMS entity/entities associated with a
    WHO Foundation URI.

    The semantic bridge is:

        who_icd_entity.foundation_uri

            ->

        who_icd_mms_entity.source_foundation_uri

    MMS text is retrieved from who_icd_mms_text rather than
    indirectly from Foundation text.
    """

    foundation_uri = str(
        foundation_uri or ""
    ).strip()

    if not foundation_uri:
        return []

    language = (
        str(language or DEFAULT_LANGUAGE)
        .strip()
    )

    sql = text(
        """
        SELECT
            m.who_icd_mms_entity_id,
            m.dataset_version_id,
            m.mms_uri,
            m.source_foundation_uri,
            m.code,
            m.class_kind,
            m.browser_url,
            m.parent_mms_uri,
            m.created_at

        FROM terminology.who_icd_mms_entity m

        WHERE
            m.source_foundation_uri =
                :foundation_uri

        ORDER BY
            m.dataset_version_id DESC,
            m.code NULLS LAST,
            m.mms_uri
        """
    )

    with engine.connect() as conn:

        result = conn.execute(
            sql,
            {
                "foundation_uri":
                    foundation_uri,
            },
        )

        entities = _rows_to_dicts(
            result
        )

        if not entities:
            return []

        text_sql = text(
            """
            SELECT
                t.language_code,
                t.text_type,
                t.text_value

            FROM terminology.who_icd_mms_text t

            WHERE
                t.who_icd_mms_entity_id =
                    :who_icd_mms_entity_id

                AND t.language_code =
                    :language

            ORDER BY
                CASE t.text_type
                    WHEN 'title' THEN 1
                    WHEN 'definition' THEN 2
                    WHEN 'longDefinition' THEN 3
                    ELSE 4
                END,
                t.text_value
            """
        )

        output: list[dict[str, Any]] = []

        for entity in entities:

            text_result = conn.execute(
                text_sql,
                {
                    "who_icd_mms_entity_id":
                        entity[
                            "who_icd_mms_entity_id"
                        ],
                    "language":
                        language,
                },
            )

            text_rows = _rows_to_dicts(
                text_result
            )

            grouped_text = _group_text_rows(
                text_rows
            )

            output.append(
                {
                    **entity,

                    "language_code":
                        language,

                    "title":
                        _first_text(
                            grouped_text,
                            "title",
                        ),

                    "definitions":
                        grouped_text.get(
                            "definition",
                            [],
                        ),

                    "long_definitions":
                        grouped_text.get(
                            "longDefinition",
                            [],
                        ),

                    "text":
                        grouped_text,
                }
            )

    return output


# ============================================================
# 4. Get MMS Children
# ============================================================

def get_mms_children(
    *,
    engine: Engine,
    mms_uri: str,
    language: str = DEFAULT_LANGUAGE,
) -> list[dict[str, Any]]:
    """
    Retrieve direct children of an ICD-11 MMS entity.

    Example:

        Diabetes mellitus block

            -> 5A10 Type 1 diabetes mellitus
            -> 5A11 Type 2 diabetes mellitus
            -> 5A12 ...
            -> 5A13 ...
            -> 5A14 ...
            -> child block(s)

    Only direct children are returned.

    Recursive hierarchy traversal can be added later if needed.
    """

    mms_uri = str(
        mms_uri or ""
    ).strip()

    if not mms_uri:
        return []

    language = (
        str(language or DEFAULT_LANGUAGE)
        .strip()
    )

    sql = text(
        """
        SELECT
            m.who_icd_mms_entity_id,
            m.dataset_version_id,
            m.mms_uri,
            m.source_foundation_uri,
            m.code,
            m.class_kind,
            m.browser_url,
            m.parent_mms_uri,
            m.created_at,

            title_text.text_value AS title,

            definition_text.text_value
                AS definition,

            long_definition_text.text_value
                AS long_definition

        FROM terminology.who_icd_mms_entity m

        LEFT JOIN LATERAL (
            SELECT
                t.text_value

            FROM terminology.who_icd_mms_text t

            WHERE
                t.who_icd_mms_entity_id =
                    m.who_icd_mms_entity_id

                AND t.language_code =
                    :language

                AND t.text_type =
                    'title'

            ORDER BY
                t.who_icd_mms_text_id

            LIMIT 1
        ) title_text
            ON TRUE

        LEFT JOIN LATERAL (
            SELECT
                t.text_value

            FROM terminology.who_icd_mms_text t

            WHERE
                t.who_icd_mms_entity_id =
                    m.who_icd_mms_entity_id

                AND t.language_code =
                    :language

                AND t.text_type =
                    'definition'

            ORDER BY
                t.who_icd_mms_text_id

            LIMIT 1
        ) definition_text
            ON TRUE

        LEFT JOIN LATERAL (
            SELECT
                t.text_value

            FROM terminology.who_icd_mms_text t

            WHERE
                t.who_icd_mms_entity_id =
                    m.who_icd_mms_entity_id

                AND t.language_code =
                    :language

                AND t.text_type =
                    'longDefinition'

            ORDER BY
                t.who_icd_mms_text_id

            LIMIT 1
        ) long_definition_text
            ON TRUE

        WHERE
            m.parent_mms_uri =
                :mms_uri

        ORDER BY
            m.code NULLS LAST,
            title_text.text_value NULLS LAST,
            m.mms_uri
        """
    )

    with engine.connect() as conn:

        result = conn.execute(
            sql,
            {
                "mms_uri":
                    mms_uri,
                "language":
                    language,
            },
        )

        return _rows_to_dicts(
            result
        )


# ============================================================
# Optional Convenience Function
# ============================================================

def get_who_icd_evidence(
    *,
    engine: Engine,
    foundation_uri: str,
    language: str = DEFAULT_LANGUAGE,
    include_mms_children: bool = True,
) -> dict[str, Any] | None:
    """
    Build a compact WHO ICD evidence package.

    This is a convenience retrieval function only.

    It does NOT decide:
    - diagnosis
    - code correctness
    - clinical relevance
    - treatment
    - clinical action

    Those decisions belong to the clinical reasoning layer.
    """

    foundation = get_foundation_entity(
        engine=engine,
        foundation_uri=foundation_uri,
        language=language,
    )

    if foundation is None:
        return None

    mms_entities = get_mms_for_foundation(
        engine=engine,
        foundation_uri=foundation_uri,
        language=language,
    )

    mms_output: list[dict[str, Any]] = []

    for mms_entity in mms_entities:

        item = dict(
            mms_entity
        )

        if include_mms_children:

            mms_uri = item.get(
                "mms_uri"
            )

            if mms_uri:
                item["children"] = (
                    get_mms_children(
                        engine=engine,
                        mms_uri=mms_uri,
                        language=language,
                    )
                )
            else:
                item["children"] = []

        mms_output.append(
            item
        )

    return {
        "source":
            "WHO ICD",

        "language_code":
            language,

        "foundation":
            foundation,

        "mms":
            mms_output,
    }

