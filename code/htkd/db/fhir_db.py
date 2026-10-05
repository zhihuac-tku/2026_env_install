 # py code beginning


"""FHIR evidence/query capability for HTKD.

This module provides read-only access to FHIR knowledge
stored in the HTKD interoperability schema.

Responsibilities:
- Search FHIR packages and artifacts.
- Inspect authoritative FHIR artifacts.
- Search and inspect StructureDefinition elements.
- Inspect ValueSet composition.
- Inspect CodeSystem metadata.
- Search indexed CodeSystem concepts.
- Assemble FHIR evidence for higher-level agents.

This module does NOT:
- Create or configure database engines.
- Import FHIR packages.
- Call an LLM.
- Make CDC reporting decisions.
- Decide whether a new Profile, Extension, ValueSet,
  or CodeSystem should be created.

The caller supplies a SQLAlchemy Engine.

This follows the same capability-layer pattern as
htkd.db.who_icd.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


# =========================================
# CONSTANTS
# =========================================

DEFAULT_LIMIT = 10
MAX_LIMIT = 100

DEFAULT_FHIR_PACKAGE = "hl7.fhir.r4.core"


# =========================================
# INTERNAL HELPERS
# =========================================

def _normalize_query(
    query: str,
) -> str:
    """Normalize a free-text search query."""

    return " ".join(
        str(query or "").strip().split()
    )


def _normalize_limit(
    limit: int,
) -> int:
    """Keep query limits inside a safe range."""

    try:
        normalized = int(limit)
    except (TypeError, ValueError):
        normalized = DEFAULT_LIMIT

    return max(
        1,
        min(
            normalized,
            MAX_LIMIT,
        ),
    )


def _normalize_optional_text(
    value: str | None,
) -> str | None:
    """Normalize optional text parameters."""

    if value is None:
        return None

    normalized = str(value).strip()

    if not normalized:
        return None

    return normalized


def _rows_to_dicts(
    result,
) -> list[dict[str, Any]]:
    """Convert SQLAlchemy result rows to dictionaries."""

    return [
        dict(row)
        for row in result.mappings().all()
    ]


def _first_dict(
    result,
) -> dict[str, Any] | None:
    """Return the first SQLAlchemy row as a dictionary."""

    row = result.mappings().first()

    if row is None:
        return None

    return dict(row)


# =========================================
# FHIR PACKAGE
# =========================================

def get_fhir_packages(
    *,
    engine: Engine,
) -> list[dict[str, Any]]:
    """Return FHIR packages currently available in HTKD."""

    sql = text(
        """
        SELECT
            p.fhir_package_id,
            p.dataset_version_id,
            p.package_name,
            p.package_version,
            p.fhir_version,
            p.canonical_base,
            p.description,
            p.publication_status,
            p.maturity_status,
            p.publication_date,
            p.source_url,
            p.created_at
        FROM interoperability.fhir_package p
        ORDER BY
            p.package_name,
            p.package_version
        """
    )

    with engine.connect() as connection:
        result = connection.execute(sql)

        return _rows_to_dicts(
            result
        )

def get_fhir_package_dependencies(
    *,
    engine: Engine,
    package_name: str,
    package_version: str | None = None,
) -> list[dict[str, Any]]:
    """Return declared dependencies for one FHIR package."""

    package_name = _normalize_optional_text(
        package_name
    )

    package_version = _normalize_optional_text(
        package_version
    )

    if package_name is None:
        return []

    sql = text(
        """
        SELECT
            p.fhir_package_id,
            p.package_name,
            p.package_version,

            d.dependency_package_name,
            d.dependency_version,
            d.dependency_fhir_package_id,

            dp.package_name
                AS resolved_package_name,
            dp.package_version
                AS resolved_package_version,
            dp.publication_status
                AS resolved_publication_status,
            dp.maturity_status
                AS resolved_maturity_status

        FROM interoperability.fhir_package p

        JOIN interoperability.fhir_package_dependency d
            ON d.fhir_package_id =
               p.fhir_package_id

        LEFT JOIN interoperability.fhir_package dp
            ON dp.fhir_package_id =
               d.dependency_fhir_package_id

        WHERE
            p.package_name = :package_name

            AND (
                CAST(:package_version AS TEXT)
                    IS NULL
                OR p.package_version =
                    CAST(:package_version AS TEXT)
            )

        ORDER BY
            d.dependency_package_name,
            d.dependency_version
        """
    )

    params = {
        "package_name": package_name,
        "package_version": package_version,
    }

    with engine.connect() as connection:
        result = connection.execute(
            sql,
            params,
        )

        return _rows_to_dicts(
            result
        )

# =========================================
# FHIR ARTIFACT SEARCH
# =========================================

def search_fhir_artifacts(
    *,
    engine: Engine,
    query: str,
    package_name: str | None = DEFAULT_FHIR_PACKAGE,
    resource_type: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Search indexed FHIR artifacts.

    Searchable fields include:
    - artifact_id
    - canonical_url
    - name
    - title
    - type_code

    The function returns metadata only. The complete
    authoritative resource remains available through
    get_fhir_artifact().
    """

    query = _normalize_query(
        query
    )

    package_name = (
        _normalize_optional_text(
            package_name
        )
    )

    resource_type = (
        _normalize_optional_text(
            resource_type
        )
    )

    limit = _normalize_limit(
        limit
    )

    if not query:
        return []

    sql = text(
        """
        SELECT
            a.fhir_artifact_id,
            p.fhir_package_id,
            p.package_name,
            p.package_version,
            p.fhir_version,

            a.resource_type,
            a.artifact_id,
            a.canonical_url,
            a.version,
            a.name,
            a.title,
            a.status,
            a.kind,
            a.type_code,
            a.base_definition,
            a.derivation

        FROM interoperability.fhir_artifact a

        JOIN interoperability.fhir_package p
            ON p.fhir_package_id =
               a.fhir_package_id

        WHERE
            (
                a.artifact_id ILIKE :pattern
                OR a.canonical_url ILIKE :pattern
                OR a.name ILIKE :pattern
                OR a.title ILIKE :pattern
                OR a.type_code ILIKE :pattern
            )

            AND (
                CAST(:package_name AS TEXT)
                    IS NULL
                OR p.package_name =
                    CAST(:package_name AS TEXT)
            )

            AND (
                CAST(:resource_type AS TEXT)
                    IS NULL
                OR a.resource_type =
                    CAST(:resource_type AS TEXT)
            )

        ORDER BY
            CASE
                WHEN lower(a.artifact_id)
                     = lower(:query)
                THEN 0

                WHEN lower(a.name)
                     = lower(:query)
                THEN 1

                WHEN lower(a.type_code)
                     = lower(:query)
                THEN 2

                ELSE 3
            END,
            a.resource_type,
            a.artifact_id

        LIMIT :limit
        """
    )

    params = {
        "query": query,
        "pattern": f"%{query}%",
        "package_name": package_name,
        "resource_type": resource_type,
        "limit": limit,
    }

    with engine.connect() as connection:
        result = connection.execute(
            sql,
            params,
        )

        return _rows_to_dicts(
            result
        )


# =========================================
# GET FHIR ARTIFACT
# =========================================

def get_fhir_artifact(
    *,
    engine: Engine,
    artifact_id: str | None = None,
    canonical_url: str | None = None,
    resource_type: str | None = None,
    package_name: str | None = DEFAULT_FHIR_PACKAGE,
) -> dict[str, Any] | None:
    """Get one authoritative FHIR artifact.

    At least artifact_id or canonical_url must be supplied.

    raw_json is returned because it remains the
    authoritative representation stored by HTKD.
    """

    artifact_id = (
        _normalize_optional_text(
            artifact_id
        )
    )

    canonical_url = (
        _normalize_optional_text(
            canonical_url
        )
    )

    resource_type = (
        _normalize_optional_text(
            resource_type
        )
    )

    package_name = (
        _normalize_optional_text(
            package_name
        )
    )

    if (
        artifact_id is None
        and canonical_url is None
    ):
        raise ValueError(
            "artifact_id or canonical_url "
            "is required."
        )

    sql = text(
        """
        SELECT
            a.fhir_artifact_id,
            p.fhir_package_id,
            p.package_name,
            p.package_version,
            p.fhir_version,
            p.canonical_base,

            a.resource_type,
            a.artifact_id,
            a.canonical_url,
            a.version,
            a.name,
            a.title,
            a.status,
            a.kind,
            a.type_code,
            a.base_definition,
            a.derivation,
            a.raw_json

        FROM interoperability.fhir_artifact a

        JOIN interoperability.fhir_package p
            ON p.fhir_package_id =
               a.fhir_package_id

        WHERE
            (
                CAST(:artifact_id AS TEXT)
                    IS NULL
                OR a.artifact_id =
                    CAST(:artifact_id AS TEXT)
            )

            AND (
                CAST(:canonical_url AS TEXT)
                    IS NULL
                OR a.canonical_url =
                    CAST(:canonical_url AS TEXT)
            )

            AND (
                CAST(:resource_type AS TEXT)
                    IS NULL
                OR a.resource_type =
                    CAST(:resource_type AS TEXT)
            )

            AND (
                CAST(:package_name AS TEXT)
                    IS NULL
                OR p.package_name =
                    CAST(:package_name AS TEXT)
            )

        ORDER BY
            p.package_version DESC

        LIMIT 1
        """
    )

    params = {
        "artifact_id": artifact_id,
        "canonical_url": canonical_url,
        "resource_type": resource_type,
        "package_name": package_name,
    }

    with engine.connect() as connection:
        result = connection.execute(
            sql,
            params,
        )

        return _first_dict(
            result
        )


# =========================================
# FHIR ELEMENT SEARCH
# =========================================

def search_fhir_elements(
    *,
    engine: Engine,
    query: str,
    resource_name: str | None = None,
    package_name: str | None = DEFAULT_FHIR_PACKAGE,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Search StructureDefinition elements.

    Examples:
        query="onset"
        resource_name="Condition"

        query="subject"
        resource_name="Condition"

        query="identifier"
        resource_name="Patient"
    """

    query = _normalize_query(
        query
    )

    resource_name = (
        _normalize_optional_text(
            resource_name
        )
    )

    package_name = (
        _normalize_optional_text(
            package_name
        )
    )

    limit = _normalize_limit(
        limit
    )

    if not query:
        return []

    sql = text(
        """
        SELECT
            e.fhir_element_id,
            e.fhir_artifact_id,

            p.package_name,
            p.package_version,
            p.fhir_version,

            a.artifact_id,
            a.canonical_url,
            a.name AS artifact_name,
            a.title AS artifact_title,
            a.type_code,

            e.element_id,
            e.path,
            e.slice_name,
            e.min_cardinality,
            e.max_cardinality,
            e.type_codes,
            e.target_profiles,
            e.short_description,
            e.definition,
            e.requirements,
            e.must_support,
            e.is_modifier,
            e.is_summary,
            e.binding_strength,
            e.binding_value_set

        FROM interoperability.fhir_element e

        JOIN interoperability.fhir_artifact a
            ON a.fhir_artifact_id =
               e.fhir_artifact_id

        JOIN interoperability.fhir_package p
            ON p.fhir_package_id =
               a.fhir_package_id

        WHERE
            a.resource_type =
                'StructureDefinition'

            AND (
                e.path ILIKE :pattern
                OR e.element_id ILIKE :pattern
                OR e.short_description
                    ILIKE :pattern
                OR e.definition
                    ILIKE :pattern
            )

            AND (
                CAST(:resource_name AS TEXT)
                    IS NULL
                OR a.type_code =
                    CAST(:resource_name AS TEXT)
                OR a.artifact_id =
                    CAST(:resource_name AS TEXT)
                OR e.path ILIKE (
                    CAST(:resource_name AS TEXT)
                    || '.%'
                )
            )

            AND (
                CAST(:package_name AS TEXT)
                    IS NULL
                OR p.package_name =
                    CAST(:package_name AS TEXT)
            )

        ORDER BY
            CASE
                WHEN lower(e.path)
                     = lower(:query)
                THEN 0

                WHEN lower(e.path)
                     = lower(
                         COALESCE(
                             CAST(
                                 :resource_name
                                 AS TEXT
                             ),
                             ''
                         )
                         || '.'
                         || :query
                     )
                THEN 1

                WHEN lower(e.element_id)
                     = lower(:query)
                THEN 2

                ELSE 3
            END,
            e.path

        LIMIT :limit
        """
    )

    params = {
        "query": query,
        "pattern": f"%{query}%",
        "resource_name": resource_name,
        "package_name": package_name,
        "limit": limit,
    }

    with engine.connect() as connection:
        result = connection.execute(
            sql,
            params,
        )

        return _rows_to_dicts(
            result
        )


# =========================================
# GET FHIR ELEMENT
# =========================================

def get_fhir_element(
    *,
    engine: Engine,
    path: str,
    package_name: str | None = DEFAULT_FHIR_PACKAGE,
    artifact_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get FHIR element definitions by exact path.

    A list is returned because profiles and slices can
    legitimately define the same FHIR path.
    """

    path = _normalize_query(
        path
    )

    package_name = (
        _normalize_optional_text(
            package_name
        )
    )

    artifact_id = (
        _normalize_optional_text(
            artifact_id
        )
    )

    if not path:
        return []

    sql = text(
        """
        SELECT
            e.fhir_element_id,
            e.fhir_artifact_id,

            p.package_name,
            p.package_version,
            p.fhir_version,

            a.artifact_id,
            a.canonical_url,
            a.name AS artifact_name,
            a.title AS artifact_title,
            a.type_code,

            e.element_id,
            e.path,
            e.slice_name,
            e.min_cardinality,
            e.max_cardinality,
            e.type_codes,
            e.target_profiles,
            e.short_description,
            e.definition,
            e.requirements,
            e.must_support,
            e.is_modifier,
            e.is_summary,
            e.binding_strength,
            e.binding_value_set

        FROM interoperability.fhir_element e

        JOIN interoperability.fhir_artifact a
            ON a.fhir_artifact_id =
               e.fhir_artifact_id

        JOIN interoperability.fhir_package p
            ON p.fhir_package_id =
               a.fhir_package_id

        WHERE
            e.path = :path

            AND (
                CAST(:artifact_id AS TEXT)
                    IS NULL
                OR a.artifact_id =
                    CAST(:artifact_id AS TEXT)
            )

            AND (
                CAST(:package_name AS TEXT)
                    IS NULL
                OR p.package_name =
                    CAST(:package_name AS TEXT)
            )

        ORDER BY
            a.artifact_id,
            e.slice_name NULLS FIRST,
            e.fhir_element_id
        """
    )

    params = {
        "path": path,
        "artifact_id": artifact_id,
        "package_name": package_name,
    }

    with engine.connect() as connection:
        result = connection.execute(
            sql,
            params,
        )

        return _rows_to_dicts(
            result
        )


# =========================================
# VALUESET
# =========================================

def get_fhir_valueset(
    *,
    engine: Engine,
    artifact_id: str | None = None,
    canonical_url: str | None = None,
    package_name: str | None = DEFAULT_FHIR_PACKAGE,
) -> dict[str, Any] | None:
    """Get one authoritative FHIR ValueSet."""

    return get_fhir_artifact(
        engine=engine,
        artifact_id=artifact_id,
        canonical_url=canonical_url,
        resource_type="ValueSet",
        package_name=package_name,
    )


def get_fhir_valueset_compose(
    *,
    engine: Engine,
    artifact_id: str | None = None,
    canonical_url: str | None = None,
    package_name: str | None = DEFAULT_FHIR_PACKAGE,
) -> list[dict[str, Any]]:
    """Get indexed ValueSet include/exclude rules."""

    artifact_id = (
        _normalize_optional_text(
            artifact_id
        )
    )

    canonical_url = (
        _normalize_optional_text(
            canonical_url
        )
    )

    package_name = (
        _normalize_optional_text(
            package_name
        )
    )

    if (
        artifact_id is None
        and canonical_url is None
    ):
        raise ValueError(
            "artifact_id or canonical_url "
            "is required."
        )

    sql = text(
        """
        SELECT
            v.fhir_valueset_compose_id,
            v.fhir_artifact_id,

            p.package_name,
            p.package_version,
            p.fhir_version,

            a.artifact_id,
            a.canonical_url,
            a.name,
            a.title,
            a.status,

            v.compose_type,
            v.sequence_no,
            v.system,
            v.system_version,
            v.value_sets,
            v.concepts,
            v.filters,
            v.compose_json

        FROM interoperability.fhir_valueset_compose v

        JOIN interoperability.fhir_artifact a
            ON a.fhir_artifact_id =
               v.fhir_artifact_id

        JOIN interoperability.fhir_package p
            ON p.fhir_package_id =
               a.fhir_package_id

        WHERE
            a.resource_type =
                'ValueSet'

            AND (
                CAST(:artifact_id AS TEXT)
                    IS NULL
                OR a.artifact_id =
                    CAST(:artifact_id AS TEXT)
            )

            AND (
                CAST(:canonical_url AS TEXT)
                    IS NULL
                OR a.canonical_url =
                    CAST(:canonical_url AS TEXT)
            )

            AND (
                CAST(:package_name AS TEXT)
                    IS NULL
                OR p.package_name =
                    CAST(:package_name AS TEXT)
            )

        ORDER BY
            CASE
                WHEN v.compose_type =
                    'include'
                THEN 0
                ELSE 1
            END,
            v.sequence_no
        """
    )

    params = {
        "artifact_id": artifact_id,
        "canonical_url": canonical_url,
        "package_name": package_name,
    }

    with engine.connect() as connection:
        result = connection.execute(
            sql,
            params,
        )

        return _rows_to_dicts(
            result
        )


# =========================================
# CODESYSTEM
# =========================================

def get_fhir_codesystem(
    *,
    engine: Engine,
    artifact_id: str | None = None,
    canonical_url: str | None = None,
    package_name: str | None = DEFAULT_FHIR_PACKAGE,
) -> dict[str, Any] | None:
    """Get one authoritative FHIR CodeSystem."""

    return get_fhir_artifact(
        engine=engine,
        artifact_id=artifact_id,
        canonical_url=canonical_url,
        resource_type="CodeSystem",
        package_name=package_name,
    )


# =========================================
# FHIR CONCEPT SEARCH
# =========================================

def search_fhir_concepts(
    *,
    engine: Engine,
    query: str,
    codesystem_artifact_id: str | None = None,
    codesystem_url: str | None = None,
    package_name: str | None = DEFAULT_FHIR_PACKAGE,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Search indexed concepts supplied by FHIR CodeSystems.

    Important:
    This searches concepts actually present in imported
    CodeSystem.concept[] data.

    It does not imply that externally referenced systems,
    such as SNOMED CT with content='not-present', are
    locally available through this table.
    """

    query = _normalize_query(
        query
    )

    codesystem_artifact_id = (
        _normalize_optional_text(
            codesystem_artifact_id
        )
    )

    codesystem_url = (
        _normalize_optional_text(
            codesystem_url
        )
    )

    package_name = (
        _normalize_optional_text(
            package_name
        )
    )

    limit = _normalize_limit(
        limit
    )

    if not query:
        return []

    sql = text(
        """
        SELECT
            c.fhir_concept_id,
            c.fhir_artifact_id,

            p.package_name,
            p.package_version,
            p.fhir_version,

            a.artifact_id AS codesystem_artifact_id,
            a.canonical_url AS codesystem_url,
            a.name AS codesystem_name,
            a.title AS codesystem_title,

            c.code,
            c.display,
            c.definition,
            c.parent_code,
            c.concept_level,
            c.inactive,
            c.concept_json

        FROM interoperability.fhir_concept c

        JOIN interoperability.fhir_artifact a
            ON a.fhir_artifact_id =
               c.fhir_artifact_id

        JOIN interoperability.fhir_package p
            ON p.fhir_package_id =
               a.fhir_package_id

        WHERE
            a.resource_type =
                'CodeSystem'

            AND (
                c.code ILIKE :pattern
                OR c.display ILIKE :pattern
                OR c.definition ILIKE :pattern
            )

            AND (
                CAST(
                    :codesystem_artifact_id
                    AS TEXT
                )
                    IS NULL
                OR a.artifact_id =
                    CAST(
                        :codesystem_artifact_id
                        AS TEXT
                    )
            )

            AND (
                CAST(:codesystem_url AS TEXT)
                    IS NULL
                OR a.canonical_url =
                    CAST(:codesystem_url AS TEXT)
            )

            AND (
                CAST(:package_name AS TEXT)
                    IS NULL
                OR p.package_name =
                    CAST(:package_name AS TEXT)
            )

        ORDER BY
            CASE
                WHEN lower(c.code)
                     = lower(:query)
                THEN 0

                WHEN lower(c.display)
                     = lower(:query)
                THEN 1

                ELSE 2
            END,
            c.concept_level,
            c.code

        LIMIT :limit
        """
    )

    params = {
        "query": query,
        "pattern": f"%{query}%",
        "codesystem_artifact_id": (
            codesystem_artifact_id
        ),
        "codesystem_url": (
            codesystem_url
        ),
        "package_name": package_name,
        "limit": limit,
    }

    with engine.connect() as connection:
        result = connection.execute(
            sql,
            params,
        )

        return _rows_to_dicts(
            result
        )


# =========================================
# FHIR EVIDENCE AGGREGATOR
# =========================================

def get_fhir_evidence(
    *,
    engine: Engine,
    element_path: str | None = None,
    artifact_id: str | None = None,
    canonical_url: str | None = None,
    package_name: str | None = DEFAULT_FHIR_PACKAGE,
) -> dict[str, Any]:
    """Assemble FHIR evidence for an agent.

    This function does not interpret the evidence.
    It gathers related authoritative/indexed data.

    Typical use:
        get_fhir_evidence(
            engine=engine,
            element_path="Condition.code",
        )

    The returned object may contain:
    - matching element definitions
    - bound ValueSet
    - ValueSet compose rules
    - referenced CodeSystem metadata

    This is intentionally evidence collection rather
    than IG-design reasoning.
    """

    package_name = (
        _normalize_optional_text(
            package_name
        )
    )

    element_path = (
        _normalize_optional_text(
            element_path
        )
    )

    artifact_id = (
        _normalize_optional_text(
            artifact_id
        )
    )

    canonical_url = (
        _normalize_optional_text(
            canonical_url
        )
    )

    evidence: dict[str, Any] = {
        "package_name": package_name,
        "element_path": element_path,
        "artifact": None,
        "elements": [],
        "valuesets": [],
        "codesystems": [],
    }

    # -------------------------------------
    # Direct artifact evidence
    # -------------------------------------

    if (
        artifact_id is not None
        or canonical_url is not None
    ):
        evidence["artifact"] = (
            get_fhir_artifact(
                engine=engine,
                artifact_id=artifact_id,
                canonical_url=canonical_url,
                package_name=package_name,
            )
        )

    # -------------------------------------
    # Element evidence
    # -------------------------------------

    if element_path is None:
        return evidence

    elements = get_fhir_element(
        engine=engine,
        path=element_path,
        package_name=package_name,
    )

    evidence["elements"] = elements

    # -------------------------------------
    # Follow terminology bindings
    # -------------------------------------

    seen_valuesets: set[str] = set()
    seen_codesystems: set[str] = set()

    for element in elements:

        value_set_url = (
            element.get(
                "binding_value_set"
            )
        )

        if not value_set_url:
            continue

        value_set_url = str(
            value_set_url
        )

        if value_set_url in seen_valuesets:
            continue

        seen_valuesets.add(
            value_set_url
        )

        valueset = get_fhir_valueset(
            engine=engine,
            canonical_url=value_set_url,
            package_name=package_name,
        )

        compose = (
            get_fhir_valueset_compose(
                engine=engine,
                canonical_url=value_set_url,
                package_name=package_name,
            )
        )

        valueset_evidence = {
            "canonical_url": (
                value_set_url
            ),
            "artifact": valueset,
            "compose": compose,
        }

        evidence["valuesets"].append(
            valueset_evidence
        )

        # ---------------------------------
        # Follow CodeSystem references
        # ---------------------------------

        for rule in compose:

            system_url = rule.get(
                "system"
            )

            if not system_url:
                continue

            system_url = str(
                system_url
            )

            if system_url in seen_codesystems:
                continue

            seen_codesystems.add(
                system_url
            )

            codesystem = (
                get_fhir_codesystem(
                    engine=engine,
                    canonical_url=system_url,
                    package_name=package_name,
                )
            )

            evidence["codesystems"].append(
                {
                    "canonical_url": (
                        system_url
                    ),
                    "artifact": (
                        codesystem
                    ),
                }
            )

    return evidence

