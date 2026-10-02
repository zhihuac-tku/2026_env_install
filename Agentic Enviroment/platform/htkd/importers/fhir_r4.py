 # py code beginning

"""Import official HL7 FHIR R4 definition Bundles into HTKD.

This importer:

1. Reads an official FHIR R4 Bundle JSON file.
2. Records the import in control.import_batch.
3. Reuses the FHIR R4 package in interoperability.fhir_package.
4. Stores every authoritative FHIR resource in fhir_artifact.
5. Preserves the complete source resource in raw_json.
6. Indexes StructureDefinition.snapshot.element[] in fhir_element.
7. Indexes CodeSystem.concept[] recursively in fhir_concept.
8. Indexes ValueSet.compose.include/exclude in fhir_valueset_compose.

The importer is deterministic and does not use an LLM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from nri_code_core.db.db_runtime import (
    configure_database_runtime,
    get_engine,
)


# =========================================
# CONFIGURATION
# =========================================

DATASET_VERSION_ID = 10

PACKAGE_NAME = "hl7.fhir.r4.core"
PACKAGE_VERSION = "4.0.1"
FHIR_VERSION = "4.0.1"

CANONICAL_BASE = "http://hl7.org/fhir"

DEFAULT_SOURCE = (
    Path.home()
    / "Downloads"
    / "definitions"
    / "profiles-resources.json"
)


# =========================================
# FILE HELPERS
# =========================================

def calculate_sha256(
    path: Path,
) -> str:
    """Calculate SHA-256 checksum for the source file."""

    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            sha256.update(block)

    return sha256.hexdigest()


def load_bundle(
    path: Path,
) -> dict[str, Any]:
    """Load and minimally validate a FHIR Bundle."""

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "FHIR source JSON is not an object."
        )

    if data.get("resourceType") != "Bundle":
        raise ValueError(
            "FHIR source is not a Bundle."
        )

    entries = data.get("entry")

    if not isinstance(
        entries,
        list,
    ):
        raise ValueError(
            "FHIR Bundle does not contain entry[]."
        )

    return data


# =========================================
# STRUCTUREDEFINITION HELPERS
# =========================================

def extract_type_information(
    element: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Extract datatype codes and referenced profiles."""

    type_codes: list[str] = []
    target_profiles: list[str] = []

    type_items = element.get(
        "type",
        [],
    )

    if not isinstance(
        type_items,
        list,
    ):
        return (
            type_codes,
            target_profiles,
        )

    for type_item in type_items:
        if not isinstance(
            type_item,
            dict,
        ):
            continue

        code = type_item.get(
            "code"
        )

        if code:
            type_codes.append(
                str(code)
            )

        target_profile_values = (
            type_item.get(
                "targetProfile",
                [],
            )
        )

        if isinstance(
            target_profile_values,
            str,
        ):
            target_profile_values = [
                target_profile_values
            ]

        if isinstance(
            target_profile_values,
            list,
        ):
            for target in (
                target_profile_values
            ):
                if target:
                    target_profiles.append(
                        str(target)
                    )

        profile_values = type_item.get(
            "profile",
            [],
        )

        if isinstance(
            profile_values,
            str,
        ):
            profile_values = [
                profile_values
            ]

        if isinstance(
            profile_values,
            list,
        ):
            for target in profile_values:
                if target:
                    target_profiles.append(
                        str(target)
                    )

    type_codes = list(
        dict.fromkeys(
            type_codes
        )
    )

    target_profiles = list(
        dict.fromkeys(
            target_profiles
        )
    )

    return (
        type_codes,
        target_profiles,
    )


def extract_binding(
    element: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Extract terminology binding information."""

    binding = element.get(
        "binding"
    )

    if not isinstance(
        binding,
        dict,
    ):
        return None, None

    strength = binding.get(
        "strength"
    )

    value_set = binding.get(
        "valueSet"
    )

    if strength is not None:
        strength = str(
            strength
        )

    if value_set is not None:
        value_set = str(
            value_set
        )

    return (
        strength,
        value_set,
    )


# =========================================
# DATABASE — IMPORT BATCH
# =========================================

def create_import_batch(
    connection,
    *,
    source_checksum: str,
    source_row_count: int,
    source_file_name: str,
) -> int:
    """Create one HTKD import-batch record."""

    result = connection.execute(
        text(
            """
            INSERT INTO control.import_batch (
                dataset_version_id,
                import_status,
                source_row_count,
                imported_row_count,
                rejected_row_count,
                source_checksum,
                import_program,
                notes
            )
            VALUES (
                :dataset_version_id,
                'running',
                :source_row_count,
                0,
                0,
                :source_checksum,
                :import_program,
                :notes
            )
            RETURNING import_batch_id
            """
        ),
        {
            "dataset_version_id": (
                DATASET_VERSION_ID
            ),
            "source_row_count": (
                source_row_count
            ),
            "source_checksum": (
                source_checksum
            ),
            "import_program": (
                "htkd/importers/fhir_r4.py"
            ),
            "notes": (
                f"FHIR R4 {source_file_name}"
            ),
        },
    )

    return int(
        result.scalar_one()
    )


def complete_import_batch(
    connection,
    *,
    import_batch_id: int,
    source_file_name: str,
    artifact_count: int,
    element_count: int,
    concept_count: int,
    valueset_compose_count: int,
    rejected_count: int,
) -> None:
    """Mark one import batch as completed."""

    connection.execute(
        text(
            """
            UPDATE control.import_batch
            SET
                completed_at = now(),
                import_status = 'completed',
                imported_row_count = :imported,
                rejected_row_count = :rejected,
                notes = :notes
            WHERE import_batch_id = :import_batch_id
            """
        ),
        {
            "imported": (
                artifact_count
            ),
            "rejected": (
                rejected_count
            ),
            "notes": (
                f"Imported {source_file_name}; "
                f"artifacts={artifact_count}; "
                f"elements={element_count}; "
                f"concepts={concept_count}; "
                f"valueset_compose="
                f"{valueset_compose_count}"
            ),
            "import_batch_id": (
                import_batch_id
            ),
        },
    )


# =========================================
# DATABASE — PACKAGE / ARTIFACT
# =========================================

def get_or_create_package(
    connection,
) -> int:
    """Get or create the common FHIR R4 package."""

    result = connection.execute(
        text(
            """
            INSERT INTO interoperability.fhir_package (
                dataset_version_id,
                package_name,
                package_version,
                fhir_version,
                canonical_base,
                description
            )
            VALUES (
                :dataset_version_id,
                :package_name,
                :package_version,
                :fhir_version,
                :canonical_base,
                :description
            )
            ON CONFLICT (
                dataset_version_id,
                package_name,
                package_version
            )
            DO UPDATE SET
                fhir_version = EXCLUDED.fhir_version,
                canonical_base = EXCLUDED.canonical_base,
                description = EXCLUDED.description
            RETURNING fhir_package_id
            """
        ),
        {
            "dataset_version_id": (
                DATASET_VERSION_ID
            ),
            "package_name": (
                PACKAGE_NAME
            ),
            "package_version": (
                PACKAGE_VERSION
            ),
            "fhir_version": (
                FHIR_VERSION
            ),
            "canonical_base": (
                CANONICAL_BASE
            ),
            "description": (
                "Official HL7 FHIR R4 "
                "definition artifacts."
            ),
        },
    )

    return int(
        result.scalar_one()
    )


def insert_artifact(
    connection,
    *,
    fhir_package_id: int,
    resource: dict[str, Any],
) -> int:
    """Insert or update one authoritative FHIR artifact."""

    result = connection.execute(
        text(
            """
            INSERT INTO interoperability.fhir_artifact (
                fhir_package_id,
                resource_type,
                artifact_id,
                canonical_url,
                version,
                name,
                title,
                status,
                kind,
                type_code,
                base_definition,
                derivation,
                raw_json
            )
            VALUES (
                :fhir_package_id,
                :resource_type,
                :artifact_id,
                :canonical_url,
                :version,
                :name,
                :title,
                :status,
                :kind,
                :type_code,
                :base_definition,
                :derivation,
                CAST(:raw_json AS jsonb)
            )
            ON CONFLICT (
                fhir_package_id,
                resource_type,
                artifact_id
            )
            DO UPDATE SET
                canonical_url = EXCLUDED.canonical_url,
                version = EXCLUDED.version,
                name = EXCLUDED.name,
                title = EXCLUDED.title,
                status = EXCLUDED.status,
                kind = EXCLUDED.kind,
                type_code = EXCLUDED.type_code,
                base_definition = EXCLUDED.base_definition,
                derivation = EXCLUDED.derivation,
                raw_json = EXCLUDED.raw_json
            RETURNING fhir_artifact_id
            """
        ),
        {
            "fhir_package_id": (
                fhir_package_id
            ),
            "resource_type": (
                resource.get(
                    "resourceType"
                )
            ),
            "artifact_id": (
                resource.get(
                    "id"
                )
            ),
            "canonical_url": (
                resource.get(
                    "url"
                )
            ),
            "version": (
                resource.get(
                    "version"
                )
            ),
            "name": (
                resource.get(
                    "name"
                )
            ),
            "title": (
                resource.get(
                    "title"
                )
            ),
            "status": (
                resource.get(
                    "status"
                )
            ),
            "kind": (
                resource.get(
                    "kind"
                )
            ),
            "type_code": (
                resource.get(
                    "type"
                )
            ),
            "base_definition": (
                resource.get(
                    "baseDefinition"
                )
            ),
            "derivation": (
                resource.get(
                    "derivation"
                )
            ),
            "raw_json": json.dumps(
                resource,
                ensure_ascii=False,
            ),
        },
    )

    return int(
        result.scalar_one()
    )


# =========================================
# DATABASE — STRUCTUREDEFINITION INDEX
# =========================================

def replace_elements(
    connection,
    *,
    fhir_artifact_id: int,
    resource: dict[str, Any],
) -> int:
    """Replace indexed elements for one artifact."""

    connection.execute(
        text(
            """
            DELETE FROM interoperability.fhir_element
            WHERE fhir_artifact_id = :fhir_artifact_id
            """
        ),
        {
            "fhir_artifact_id": (
                fhir_artifact_id
            )
        },
    )

    if (
        resource.get(
            "resourceType"
        )
        != "StructureDefinition"
    ):
        return 0

    snapshot = resource.get(
        "snapshot"
    )

    if not isinstance(
        snapshot,
        dict,
    ):
        return 0

    elements = snapshot.get(
        "element",
        [],
    )

    if not isinstance(
        elements,
        list,
    ):
        return 0

    inserted = 0

    for element in elements:
        if not isinstance(
            element,
            dict,
        ):
            continue

        path = element.get(
            "path"
        )

        if not path:
            continue

        (
            type_codes,
            target_profiles,
        ) = extract_type_information(
            element
        )

        (
            binding_strength,
            binding_value_set,
        ) = extract_binding(
            element
        )

        connection.execute(
            text(
                """
                INSERT INTO interoperability.fhir_element (
                    fhir_artifact_id,
                    element_id,
                    path,
                    slice_name,
                    min_cardinality,
                    max_cardinality,
                    type_codes,
                    target_profiles,
                    short_description,
                    definition,
                    requirements,
                    must_support,
                    is_modifier,
                    is_summary,
                    binding_strength,
                    binding_value_set
                )
                VALUES (
                    :fhir_artifact_id,
                    :element_id,
                    :path,
                    :slice_name,
                    :min_cardinality,
                    :max_cardinality,
                    CAST(:type_codes AS jsonb),
                    CAST(:target_profiles AS jsonb),
                    :short_description,
                    :definition,
                    :requirements,
                    :must_support,
                    :is_modifier,
                    :is_summary,
                    :binding_strength,
                    :binding_value_set
                )
                """
            ),
            {
                "fhir_artifact_id": (
                    fhir_artifact_id
                ),
                "element_id": (
                    element.get(
                        "id"
                    )
                ),
                "path": (
                    path
                ),
                "slice_name": (
                    element.get(
                        "sliceName"
                    )
                ),
                "min_cardinality": (
                    element.get(
                        "min"
                    )
                ),
                "max_cardinality": (
                    element.get(
                        "max"
                    )
                ),
                "type_codes": json.dumps(
                    type_codes,
                    ensure_ascii=False,
                ),
                "target_profiles": json.dumps(
                    target_profiles,
                    ensure_ascii=False,
                ),
                "short_description": (
                    element.get(
                        "short"
                    )
                ),
                "definition": (
                    element.get(
                        "definition"
                    )
                ),
                "requirements": (
                    element.get(
                        "requirements"
                    )
                ),
                "must_support": (
                    element.get(
                        "mustSupport"
                    )
                ),
                "is_modifier": (
                    element.get(
                        "isModifier"
                    )
                ),
                "is_summary": (
                    element.get(
                        "isSummary"
                    )
                ),
                "binding_strength": (
                    binding_strength
                ),
                "binding_value_set": (
                    binding_value_set
                ),
            },
        )

        inserted += 1

    return inserted


# =========================================
# DATABASE — CODESYSTEM CONCEPT INDEX
# =========================================

def _insert_concept_tree(
    connection,
    *,
    fhir_artifact_id: int,
    concepts: list[Any],
    parent_code: str | None = None,
    concept_level: int = 0,
) -> int:
    """Recursively index CodeSystem.concept[]."""

    inserted = 0

    for concept in concepts:
        if not isinstance(
            concept,
            dict,
        ):
            continue

        code = concept.get(
            "code"
        )

        if not code:
            continue

        inactive = None

        properties = concept.get(
            "property",
            [],
        )

        if isinstance(
            properties,
            list,
        ):
            for prop in properties:
                if not isinstance(
                    prop,
                    dict,
                ):
                    continue

                if (
                    prop.get("code")
                    == "inactive"
                ):
                    value = prop.get(
                        "valueBoolean"
                    )

                    if isinstance(
                        value,
                        bool,
                    ):
                        inactive = value

        connection.execute(
            text(
                """
                INSERT INTO interoperability.fhir_concept (
                    fhir_artifact_id,
                    code,
                    display,
                    definition,
                    parent_code,
                    concept_level,
                    inactive,
                    concept_json
                )
                VALUES (
                    :fhir_artifact_id,
                    :code,
                    :display,
                    :definition,
                    :parent_code,
                    :concept_level,
                    :inactive,
                    CAST(:concept_json AS jsonb)
                )
                """
            ),
            {
                "fhir_artifact_id": (
                    fhir_artifact_id
                ),
                "code": str(
                    code
                ),
                "display": (
                    concept.get(
                        "display"
                    )
                ),
                "definition": (
                    concept.get(
                        "definition"
                    )
                ),
                "parent_code": (
                    parent_code
                ),
                "concept_level": (
                    concept_level
                ),
                "inactive": (
                    inactive
                ),
                "concept_json": json.dumps(
                    concept,
                    ensure_ascii=False,
                ),
            },
        )

        inserted += 1

        child_concepts = concept.get(
            "concept",
            [],
        )

        if isinstance(
            child_concepts,
            list,
        ):
            inserted += (
                _insert_concept_tree(
                    connection,
                    fhir_artifact_id=(
                        fhir_artifact_id
                    ),
                    concepts=(
                        child_concepts
                    ),
                    parent_code=str(
                        code
                    ),
                    concept_level=(
                        concept_level + 1
                    ),
                )
            )

    return inserted


def replace_concepts(
    connection,
    *,
    fhir_artifact_id: int,
    resource: dict[str, Any],
) -> int:
    """Replace searchable concepts for a CodeSystem."""

    connection.execute(
        text(
            """
            DELETE FROM interoperability.fhir_concept
            WHERE fhir_artifact_id = :fhir_artifact_id
            """
        ),
        {
            "fhir_artifact_id": (
                fhir_artifact_id
            )
        },
    )

    if (
        resource.get(
            "resourceType"
        )
        != "CodeSystem"
    ):
        return 0

    concepts = resource.get(
        "concept",
        [],
    )

    if not isinstance(
        concepts,
        list,
    ):
        return 0

    return _insert_concept_tree(
        connection,
        fhir_artifact_id=(
            fhir_artifact_id
        ),
        concepts=concepts,
    )


# =========================================
# DATABASE — VALUESET COMPOSE INDEX
# =========================================

def replace_valueset_compose(
    connection,
    *,
    fhir_artifact_id: int,
    resource: dict[str, Any],
) -> int:
    """Replace searchable ValueSet compose rules."""

    connection.execute(
        text(
            """
            DELETE FROM interoperability.fhir_valueset_compose
            WHERE fhir_artifact_id = :fhir_artifact_id
            """
        ),
        {
            "fhir_artifact_id": (
                fhir_artifact_id
            )
        },
    )

    if (
        resource.get(
            "resourceType"
        )
        != "ValueSet"
    ):
        return 0

    compose = resource.get(
        "compose"
    )

    if not isinstance(
        compose,
        dict,
    ):
        return 0

    inserted = 0

    for compose_type in (
        "include",
        "exclude",
    ):
        compose_items = compose.get(
            compose_type,
            [],
        )

        if not isinstance(
            compose_items,
            list,
        ):
            continue

        for sequence_no, item in enumerate(
            compose_items,
            start=1,
        ):
            if not isinstance(
                item,
                dict,
            ):
                continue

            value_sets = item.get(
                "valueSet",
                [],
            )

            if isinstance(
                value_sets,
                str,
            ):
                value_sets = [
                    value_sets
                ]

            if not isinstance(
                value_sets,
                list,
            ):
                value_sets = []

            concepts = item.get(
                "concept",
                [],
            )

            if not isinstance(
                concepts,
                list,
            ):
                concepts = []

            filters = item.get(
                "filter",
                [],
            )

            if not isinstance(
                filters,
                list,
            ):
                filters = []

            connection.execute(
                text(
                    """
                    INSERT INTO interoperability.fhir_valueset_compose (
                        fhir_artifact_id,
                        compose_type,
                        sequence_no,
                        system,
                        system_version,
                        value_sets,
                        concepts,
                        filters,
                        compose_json
                    )
                    VALUES (
                        :fhir_artifact_id,
                        :compose_type,
                        :sequence_no,
                        :system,
                        :system_version,
                        CAST(:value_sets AS jsonb),
                        CAST(:concepts AS jsonb),
                        CAST(:filters AS jsonb),
                        CAST(:compose_json AS jsonb)
                    )
                    """
                ),
                {
                    "fhir_artifact_id": (
                        fhir_artifact_id
                    ),
                    "compose_type": (
                        compose_type
                    ),
                    "sequence_no": (
                        sequence_no
                    ),
                    "system": (
                        item.get(
                            "system"
                        )
                    ),
                    "system_version": (
                        item.get(
                            "version"
                        )
                    ),
                    "value_sets": json.dumps(
                        value_sets,
                        ensure_ascii=False,
                    ),
                    "concepts": json.dumps(
                        concepts,
                        ensure_ascii=False,
                    ),
                    "filters": json.dumps(
                        filters,
                        ensure_ascii=False,
                    ),
                    "compose_json": json.dumps(
                        item,
                        ensure_ascii=False,
                    ),
                },
            )

            inserted += 1

    return inserted


# =========================================
# IMPORT
# =========================================

def import_fhir_r4(
    *,
    source_path: Path,
) -> None:
    """Import one official FHIR R4 definition Bundle."""

    source_path = (
        source_path
        .expanduser()
        .resolve()
    )

    if not source_path.exists():
        raise FileNotFoundError(
            source_path
        )

    if not source_path.is_file():
        raise ValueError(
            f"Source is not a file: "
            f"{source_path}"
        )

    print(
        f"Source: {source_path}"
    )

    print(
        "Reading FHIR R4 bundle..."
    )

    bundle = load_bundle(
        source_path
    )

    entries = bundle.get(
        "entry",
        [],
    )

    print(
        f"Bundle id: "
        f"{bundle.get('id')}"
    )

    print(
        f"Bundle type: "
        f"{bundle.get('type')}"
    )

    print(
        f"Bundle entries: "
        f"{len(entries)}"
    )

    checksum = calculate_sha256(
        source_path
    )

    print(
        f"SHA-256: {checksum}"
    )

    # -------------------------------------
    # Shared NRI database runtime
    # -------------------------------------

    configure_database_runtime(
        db_name="htkd_db",
        default_env="MacBook",
        intranet_host="192.168.184.13",
        intranet_port=5432,
    )

    # CLI importer: use the established
    # MacBook HTKD PostgreSQL endpoint.
    dsn = (
        "postgresql+psycopg2://"
        "app_admin@127.0.0.1:55436/"
        "htkd_db"
    )

    engine = get_engine(
        dsn
    )

    artifact_count = 0
    element_count = 0
    concept_count = 0
    valueset_compose_count = 0
    rejected_count = 0

    import_batch_id: int | None = None

    try:
        with engine.begin() as connection:

            # ---------------------------------
            # Import provenance
            # ---------------------------------

            import_batch_id = (
                create_import_batch(
                    connection,
                    source_checksum=checksum,
                    source_row_count=len(
                        entries
                    ),
                    source_file_name=(
                        source_path.name
                    ),
                )
            )

            # ---------------------------------
            # Common FHIR R4 package
            # ---------------------------------

            fhir_package_id = (
                get_or_create_package(
                    connection
                )
            )

            print(
                "Import batch:",
                import_batch_id,
            )

            print(
                "FHIR package:",
                fhir_package_id,
            )

            # ---------------------------------
            # Bundle entries
            # ---------------------------------

            for index, entry in enumerate(
                entries,
                start=1,
            ):
                if not isinstance(
                    entry,
                    dict,
                ):
                    rejected_count += 1
                    continue

                resource = entry.get(
                    "resource"
                )

                if not isinstance(
                    resource,
                    dict,
                ):
                    rejected_count += 1
                    continue

                resource_type = (
                    resource.get(
                        "resourceType"
                    )
                )

                artifact_id = (
                    resource.get(
                        "id"
                    )
                )

                if (
                    not resource_type
                    or not artifact_id
                ):
                    rejected_count += 1
                    continue

                # -----------------------------
                # Authoritative artifact
                # -----------------------------

                fhir_artifact_id = (
                    insert_artifact(
                        connection,
                        fhir_package_id=(
                            fhir_package_id
                        ),
                        resource=resource,
                    )
                )

                artifact_count += 1

                # -----------------------------
                # StructureDefinition index
                # -----------------------------

                if (
                    resource_type
                    == "StructureDefinition"
                ):
                    element_count += (
                        replace_elements(
                            connection,
                            fhir_artifact_id=(
                                fhir_artifact_id
                            ),
                            resource=resource,
                        )
                    )

                # -----------------------------
                # CodeSystem index
                # -----------------------------

                elif (
                    resource_type
                    == "CodeSystem"
                ):
                    concept_count += (
                        replace_concepts(
                            connection,
                            fhir_artifact_id=(
                                fhir_artifact_id
                            ),
                            resource=resource,
                        )
                    )

                # -----------------------------
                # ValueSet index
                # -----------------------------

                elif (
                    resource_type
                    == "ValueSet"
                ):
                    valueset_compose_count += (
                        replace_valueset_compose(
                            connection,
                            fhir_artifact_id=(
                                fhir_artifact_id
                            ),
                            resource=resource,
                        )
                    )

                # -----------------------------
                # Progress
                # -----------------------------

                if (
                    index % 100 == 0
                    or index == len(
                        entries
                    )
                ):
                    print(
                        f"[{index}/{len(entries)}] "
                        f"artifacts="
                        f"{artifact_count}, "
                        f"elements="
                        f"{element_count}, "
                        f"concepts="
                        f"{concept_count}, "
                        f"valueset_compose="
                        f"{valueset_compose_count}, "
                        f"rejected="
                        f"{rejected_count}"
                    )

            # ---------------------------------
            # Complete provenance
            # ---------------------------------

            complete_import_batch(
                connection,
                import_batch_id=(
                    import_batch_id
                ),
                source_file_name=(
                    source_path.name
                ),
                artifact_count=(
                    artifact_count
                ),
                element_count=(
                    element_count
                ),
                concept_count=(
                    concept_count
                ),
                valueset_compose_count=(
                    valueset_compose_count
                ),
                rejected_count=(
                    rejected_count
                ),
            )

    except Exception:
        print()
        print(
            "FHIR R4 import failed."
        )

        if import_batch_id is not None:
            print(
                "Import batch:",
                import_batch_id,
            )

        raise

    print()
    print(
        "FHIR R4 import completed."
    )

    print(
        "Source file:",
        source_path.name,
    )

    print(
        "Artifacts:",
        artifact_count,
    )

    print(
        "Elements:",
        element_count,
    )

    print(
        "Concepts:",
        concept_count,
    )

    print(
        "ValueSet compose rows:",
        valueset_compose_count,
    )

    print(
        "Rejected:",
        rejected_count,
    )


# =========================================
# CLI
# =========================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import an official FHIR R4 "
            "definition Bundle into HTKD."
        )
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=(
            "Path to an official FHIR R4 "
            "definition Bundle JSON file."
        ),
    )

    args = parser.parse_args()

    import_fhir_r4(
        source_path=args.source,
    )


if __name__ == "__main__":
    main()

