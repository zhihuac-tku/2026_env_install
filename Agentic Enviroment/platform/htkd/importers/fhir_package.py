 # py code beginning

"""Import a versioned FHIR NPM package (.tgz) into HTKD.

Designed for packages such as:
- tw.gov.mohw.twcore
- tw.gov.mohw.cdc.nidrs
- tw.gov.mohw.cdc.twidir

The importer is deterministic and does not use an LLM.

It preserves each top-level FHIR JSON resource as authoritative raw_json
and reuses the proven indexing helpers from htkd.importers.fhir_r4 for:
- StructureDefinition.snapshot.element[]
- CodeSystem.concept[]
- ValueSet.compose.include/exclude

Examples and generated support files are intentionally excluded in V1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from htkd.db.htkd_db import (
    complete_import_batch,
    create_import_batch,
    fail_import_batch,
    get_htkd_engine,
)
from htkd.importers.fhir_r4 import (
    insert_artifact,
    replace_concepts,
    replace_elements,
    replace_valueset_compose,
)


# =========================================
# MODELS
# =========================================

@dataclass(frozen=True)
class FHIRPackageMetadata:
    package_name: str
    package_version: str
    fhir_version: str | None
    canonical_base: str | None
    package_url: str | None
    title: str | None
    description: str | None
    package_date: str | None
    publication_date: str | None
    publication_status: str | None
    maturity_status: str | None
    dependencies: dict[str, str]


# =========================================
# FILE HELPERS
# =========================================

def calculate_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(block)
    return sha256.hexdigest()


def _load_json_bytes(data: bytes, *, member_name: str) -> dict[str, Any]:
    obj = json.loads(data.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON member is not an object: {member_name}")
    return obj


def _parse_package_date(value: Any) -> str | None:
    """Convert FHIR package date such as 20241212124159 to YYYY-MM-DD."""
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    for fmt in (
        "%Y%m%d%H%M%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass

    # Handles ISO timestamps with timezone colon on supported Python versions.
    try:
        return datetime.fromisoformat(raw).date().isoformat()
    except ValueError:
        return None


def _extract_release_label(
    implementation_guide: dict[str, Any] | None,
) -> str | None:
    if not implementation_guide:
        return None

    definition = implementation_guide.get("definition")
    if not isinstance(definition, dict):
        return None

    extensions = definition.get("extension", [])
    if not isinstance(extensions, list):
        return None

    for outer in extensions:
        if not isinstance(outer, dict):
            continue
        nested = outer.get("extension", [])
        if not isinstance(nested, list):
            continue

        code = None
        value = None
        for item in nested:
            if not isinstance(item, dict):
                continue
            if item.get("url") == "code":
                code = item.get("valueString")
            elif item.get("url") == "value":
                value = (
                    item.get("valueString")
                    or item.get("valueCode")
                    or item.get("valueMarkdown")
                )

        if code == "releaselabel" and value:
            return str(value)

    return None


def _normalize_maturity_status(release_label: str | None) -> str | None:
    if not release_label:
        return None

    value = release_label.strip().lower()

    if "trial use" in value or "trial-use" in value or value == "stu":
        return "trial-use"
    if "normative" in value:
        return "normative"
    if "draft" in value:
        return "draft"

    return release_label.strip()


def _find_implementation_guide(
    tar: tarfile.TarFile,
) -> dict[str, Any] | None:
    candidates = [
        m
        for m in tar.getmembers()
        if (
            m.isfile()
            and m.name.startswith("package/ImplementationGuide-")
            and m.name.endswith(".json")
            and "/" not in m.name[len("package/"):]
        )
    ]

    if not candidates:
        return None

    member = candidates[0]
    f = tar.extractfile(member)
    if f is None:
        return None

    resource = _load_json_bytes(
        f.read(),
        member_name=member.name,
    )

    if resource.get("resourceType") != "ImplementationGuide":
        return None

    return resource


def read_package_metadata(
    source_path: Path,
) -> FHIRPackageMetadata:
    with tarfile.open(source_path, "r:gz") as tar:
        try:
            member = tar.getmember("package/package.json")
        except KeyError as exc:
            raise ValueError(
                "FHIR NPM package does not contain package/package.json."
            ) from exc

        f = tar.extractfile(member)
        if f is None:
            raise ValueError("Unable to read package/package.json.")

        package_json = _load_json_bytes(
            f.read(),
            member_name=member.name,
        )

        package_name = str(package_json.get("name") or "").strip()
        package_version = str(package_json.get("version") or "").strip()

        if not package_name or not package_version:
            raise ValueError(
                "package.json must contain non-empty name and version."
            )

        fhir_versions = package_json.get("fhirVersions", [])
        fhir_version = None
        if isinstance(fhir_versions, list) and fhir_versions:
            fhir_version = str(fhir_versions[0])
        elif isinstance(fhir_versions, str):
            fhir_version = fhir_versions

        dependencies_raw = package_json.get("dependencies", {})
        dependencies: dict[str, str] = {}
        if isinstance(dependencies_raw, dict):
            for name, version in dependencies_raw.items():
                if name and version:
                    dependencies[str(name)] = str(version)

        implementation_guide = _find_implementation_guide(tar)
        release_label = _extract_release_label(implementation_guide)

        publication_date = None
        if implementation_guide:
            publication_date = _parse_package_date(
                implementation_guide.get("date")
            )
        if publication_date is None:
            publication_date = _parse_package_date(
                package_json.get("date")
            )

        # A fixed version-specific NPM package is stored as a published package
        # in HTKD. FHIR resource status (e.g. active) remains in raw_json.
        not_for_publication = bool(
            package_json.get(
                "notForPublication",
                False,
            )
        )

        if not_for_publication:
            publication_status = "ci-build"
        else:
            publication_status = "published"

        return FHIRPackageMetadata(
            package_name=package_name,
            package_version=package_version,
            fhir_version=fhir_version,
            canonical_base=(
                str(package_json.get("canonical"))
                if package_json.get("canonical")
                else None
            ),
            package_url=(
                str(package_json.get("url"))
                if package_json.get("url")
                else None
            ),
            title=(
                str(package_json.get("title"))
                if package_json.get("title")
                else None
            ),
            description=(
                str(package_json.get("description"))
                if package_json.get("description")
                else None
            ),
            package_date=(
                str(package_json.get("date"))
                if package_json.get("date")
                else None
            ),
            publication_date=publication_date,
            publication_status=publication_status,
            maturity_status=_normalize_maturity_status(release_label),
            dependencies=dependencies,
        )


def iter_top_level_fhir_resources(
    source_path: Path,
):
    """Yield authoritative top-level package/*.json FHIR resources only."""
    with tarfile.open(source_path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue

            name = member.name

            if not name.startswith("package/"):
                continue

            relative = name[len("package/"):]

            # V1 deliberately excludes directories such as:
            # example/, openapi/, other/, etc.
            if "/" in relative:
                continue

            if not relative.endswith(".json"):
                continue

            if relative in {"package.json", ".index.json"}:
                continue

            f = tar.extractfile(member)
            if f is None:
                continue

            try:
                resource = _load_json_bytes(
                    f.read(),
                    member_name=name,
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

            if not resource.get("resourceType"):
                continue

            yield name, resource


# =========================================
# CONTROL / DATASET VERSION
# =========================================

def get_dataset_id(
    engine: Engine,
    *,
    dataset_code: str,
) -> int:
    """Resolve an existing HTKD dataset by dataset_code.

    The generic FHIR importer intentionally does not create control.dataset
    records automatically. Source/dataset registration remains an explicit
    HTKD governance step.
    """
    sql = text("""
        SELECT dataset_id
        FROM control.dataset
        WHERE dataset_code = :dataset_code
    """)

    with engine.connect() as conn:
        row = conn.execute(
            sql,
            {"dataset_code": dataset_code},
        ).scalar_one_or_none()

    if row is None:
        raise ValueError(
            f"HTKD dataset_code not found: {dataset_code}. "
            "Register the source/dataset first."
        )

    return int(row)


def get_or_create_dataset_version(
    engine: Engine,
    *,
    dataset_id: int,
    metadata: FHIRPackageMetadata,
    source_file_name: str,
) -> int:
    sql = text("""
        INSERT INTO control.dataset_version (
            dataset_id,
            version_label,
            release_date,
            source_file_name,
            source_url,
            status
        )
        VALUES (
            :dataset_id,
            :version_label,
            CAST(:release_date AS date),
            :source_file_name,
            :source_url,
            'active'
        )
        ON CONFLICT (
            dataset_id,
            version_label
        )
        DO UPDATE SET
            release_date = EXCLUDED.release_date,
            source_file_name = EXCLUDED.source_file_name,
            source_url = EXCLUDED.source_url
        RETURNING dataset_version_id
    """)

    with engine.begin() as conn:
        value = conn.execute(
            sql,
            {
                "dataset_id": dataset_id,
                "version_label": metadata.package_version,
                "release_date": metadata.publication_date,
                "source_file_name": source_file_name,
                "source_url": metadata.package_url,
            },
        ).scalar_one()

    return int(value)


# =========================================
# FHIR PACKAGE / DEPENDENCIES
# =========================================

def get_or_create_fhir_package(
    connection,
    *,
    dataset_version_id: int,
    metadata: FHIRPackageMetadata,
) -> int:
    result = connection.execute(
        text("""
            INSERT INTO interoperability.fhir_package (
                dataset_version_id,
                package_name,
                package_version,
                fhir_version,
                canonical_base,
                description,
                publication_status,
                maturity_status,
                publication_date,
                source_url
            )
            VALUES (
                :dataset_version_id,
                :package_name,
                :package_version,
                :fhir_version,
                :canonical_base,
                :description,
                :publication_status,
                :maturity_status,
                CAST(:publication_date AS date),
                :source_url
            )
            ON CONFLICT (
                dataset_version_id,
                package_name,
                package_version
            )
            DO UPDATE SET
                fhir_version = EXCLUDED.fhir_version,
                canonical_base = EXCLUDED.canonical_base,
                description = EXCLUDED.description,
                publication_status = EXCLUDED.publication_status,
                maturity_status = EXCLUDED.maturity_status,
                publication_date = EXCLUDED.publication_date,
                source_url = EXCLUDED.source_url
            RETURNING fhir_package_id
        """),
        {
            "dataset_version_id": dataset_version_id,
            "package_name": metadata.package_name,
            "package_version": metadata.package_version,
            "fhir_version": metadata.fhir_version,
            "canonical_base": metadata.canonical_base,
            "description": metadata.description,
            "publication_status": metadata.publication_status,
            "maturity_status": metadata.maturity_status,
            "publication_date": metadata.publication_date,
            "source_url": metadata.package_url,
        },
    )

    return int(result.scalar_one())


def replace_package_dependencies(
    connection,
    *,
    fhir_package_id: int,
    dependencies: dict[str, str],
) -> int:
    connection.execute(
        text("""
            DELETE FROM interoperability.fhir_package_dependency
            WHERE fhir_package_id = :fhir_package_id
        """),
        {"fhir_package_id": fhir_package_id},
    )

    count = 0

    for package_name, package_version in dependencies.items():
        target_id = connection.execute(
            text("""
                SELECT fhir_package_id
                FROM interoperability.fhir_package
                WHERE package_name = :package_name
                  AND package_version = :package_version
                ORDER BY fhir_package_id
                LIMIT 1
            """),
            {
                "package_name": package_name,
                "package_version": package_version,
            },
        ).scalar_one_or_none()

        connection.execute(
            text("""
                INSERT INTO interoperability.fhir_package_dependency (
                    fhir_package_id,
                    dependency_package_name,
                    dependency_version,
                    dependency_fhir_package_id
                )
                VALUES (
                    :fhir_package_id,
                    :dependency_package_name,
                    :dependency_version,
                    :dependency_fhir_package_id
                )
            """),
            {
                "fhir_package_id": fhir_package_id,
                "dependency_package_name": package_name,
                "dependency_version": package_version,
                "dependency_fhir_package_id": target_id,
            },
        )

        count += 1

    return count


# =========================================
# IMPORT
# =========================================

def import_fhir_package(
    *,
    source_path: Path,
    dataset_code: str,
    environment: str = "MacBook",
) -> None:
    source_path = source_path.expanduser().resolve()

    if not source_path.exists():
        raise FileNotFoundError(source_path)

    if not source_path.is_file():
        raise ValueError(f"Source is not a file: {source_path}")

    print(f"Source: {source_path}")
    print("Reading FHIR NPM package metadata...")

    metadata = read_package_metadata(source_path)

    print(f"Package: {metadata.package_name}#{metadata.package_version}")
    print(f"FHIR version: {metadata.fhir_version}")
    print(f"Canonical: {metadata.canonical_base}")
    print(f"Publication date: {metadata.publication_date}")
    print(f"Publication status: {metadata.publication_status}")
    print(f"Maturity: {metadata.maturity_status}")
    print(f"Dependencies: {len(metadata.dependencies)}")

    resources = list(iter_top_level_fhir_resources(source_path))
    print(f"Top-level FHIR resources: {len(resources)}")

    checksum = calculate_sha256(source_path)
    print(f"SHA-256: {checksum}")

    engine = get_htkd_engine(environment)

    dataset_id = get_dataset_id(
        engine,
        dataset_code=dataset_code,
    )

    dataset_version_id = get_or_create_dataset_version(
        engine,
        dataset_id=dataset_id,
        metadata=metadata,
        source_file_name=source_path.name,
    )

    import_batch_id = create_import_batch(
        engine,
        dataset_version_id=dataset_version_id,
        source_checksum=checksum,
        import_program="htkd.importers.fhir_package",
        notes=(
            f"{metadata.package_name}#{metadata.package_version}; "
            f"source={source_path.name}"
        ),
    )

    artifact_count = 0
    element_count = 0
    concept_count = 0
    valueset_compose_count = 0
    rejected_count = 0
    dependency_count = 0

    try:
        with engine.begin() as connection:
            fhir_package_id = get_or_create_fhir_package(
                connection,
                dataset_version_id=dataset_version_id,
                metadata=metadata,
            )

            dependency_count = replace_package_dependencies(
                connection,
                fhir_package_id=fhir_package_id,
                dependencies=metadata.dependencies,
            )

            print(f"Dataset version: {dataset_version_id}")
            print(f"Import batch: {import_batch_id}")
            print(f"FHIR package: {fhir_package_id}")

            for index, (member_name, resource) in enumerate(
                resources,
                start=1,
            ):
                resource_type = resource.get("resourceType")
                artifact_id = resource.get("id")

                if not resource_type or not artifact_id:
                    rejected_count += 1
                    print(
                        f"Rejected: {member_name} "
                        "(missing resourceType or id)"
                    )
                    continue

                fhir_artifact_id = insert_artifact(
                    connection,
                    fhir_package_id=fhir_package_id,
                    resource=resource,
                )
                artifact_count += 1

                if resource_type == "StructureDefinition":
                    element_count += replace_elements(
                        connection,
                        fhir_artifact_id=fhir_artifact_id,
                        resource=resource,
                    )

                elif resource_type == "CodeSystem":
                    concept_count += replace_concepts(
                        connection,
                        fhir_artifact_id=fhir_artifact_id,
                        resource=resource,
                    )

                elif resource_type == "ValueSet":
                    valueset_compose_count += replace_valueset_compose(
                        connection,
                        fhir_artifact_id=fhir_artifact_id,
                        resource=resource,
                    )

                if index % 50 == 0 or index == len(resources):
                    print(
                        f"[{index}/{len(resources)}] "
                        f"artifacts={artifact_count}, "
                        f"elements={element_count}, "
                        f"concepts={concept_count}, "
                        f"valueset_compose={valueset_compose_count}, "
                        f"rejected={rejected_count}"
                    )

        complete_import_batch(
            engine,
            import_batch_id=import_batch_id,
            source_row_count=len(resources),
            imported_row_count=artifact_count,
            rejected_row_count=rejected_count,
        )

    except Exception as exc:
        fail_import_batch(
            engine,
            import_batch_id=import_batch_id,
            error_message=str(exc),
        )
        raise

    print()
    print("FHIR NPM package import completed.")
    print(f"Package: {metadata.package_name}#{metadata.package_version}")
    print(f"Dataset version: {dataset_version_id}")
    print(f"FHIR package ID: {fhir_package_id}")
    print(f"Dependencies: {dependency_count}")
    print(f"Artifacts: {artifact_count}")
    print(f"Elements: {element_count}")
    print(f"Concepts: {concept_count}")
    print(f"ValueSet compose rows: {valueset_compose_count}")
    print(f"Rejected: {rejected_count}")


# =========================================
# CLI
# =========================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a FHIR NPM package (.tgz) into HTKD."
    )

    parser.add_argument(
        "source",
        type=Path,
        help="Path to FHIR package.tgz.",
    )

    parser.add_argument(
        "--dataset-code",
        required=True,
        help=(
            "Existing control.dataset dataset_code, "
            "for example TW_CORE."
        ),
    )

    parser.add_argument(
        "--environment",
        default="MacBook",
        help="HTKD database environment. Default: MacBook.",
    )

    args = parser.parse_args()

    import_fhir_package(
        source_path=args.source,
        dataset_code=args.dataset_code,
        environment=args.environment,
    )


if __name__ == "__main__":
    main()

