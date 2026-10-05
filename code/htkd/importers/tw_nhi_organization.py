 # py code beginning

"""Import the Taiwan NHI healthcare-organization dataset family into HTKD.

Files handled:
- D2100G: healthcare organization master
- D2100C: organization-specialty relationships
- D2100F: specialty dictionary
- D2100H: organization-service relationships
- D2100E: service-item dictionary

The importer uses htkd.db.htkd_db, which in turn uses the shared
nri_code_core database runtime. It does not create its own DB runtime.
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text

from htkd.db.htkd_db import (
    complete_import_batch,
    create_import_batch,
    fail_import_batch,
    get_htkd_engine,
)

IMPORT_PROGRAM = "htkd.importers.tw_nhi_organization"
DEFAULT_ENVIRONMENT = "MacBook"
BATCH_SIZE = 5000


@dataclass(frozen=True)
class SourceSpec:
    key: str
    label: str
    dataset_version_id: int
    required_columns: tuple[str, ...]
    table_name: str


SPECS = {
    "g": SourceSpec(
        key="g",
        label="D2100G Organization",
        dataset_version_id=4,
        required_columns=(
            "分區業務組別代碼", "醫事機構代碼", "權屬別名稱", "醫事機構名稱",
            "機構地址", "電話區域號碼", "電話號碼", "特約類別", "型態別代碼",
            "醫事機構種類", "終止合約或歇業日期", "原始合約起始日期",
        ),
        table_name="healthcare.nhi_organization",
    ),
    "c": SourceSpec(
        key="c",
        label="D2100C Organization Specialty",
        dataset_version_id=5,
        required_columns=("醫事機構代碼", "診療科別"),
        table_name="healthcare.nhi_org_specialty",
    ),
    "f": SourceSpec(
        key="f",
        label="D2100F Specialty",
        dataset_version_id=6,
        required_columns=("診療科別", "診療科別名稱"),
        table_name="healthcare.nhi_specialty",
    ),
    "h": SourceSpec(
        key="h",
        label="D2100H Organization Service",
        dataset_version_id=7,
        required_columns=("醫事機構代碼", "機構服務項目代碼"),
        table_name="healthcare.nhi_org_service",
    ),
    "e": SourceSpec(
        key="e",
        label="D2100E Service Type",
        dataset_version_id=8,
        required_columns=("機構服務項目代碼", "機構服務項目名稱"),
        table_name="healthcare.nhi_service_type",
    ),
}


UPSERT_SQL = {
    "g": text("""
        INSERT INTO healthcare.nhi_organization (
            dataset_version_id, business_group_code, organization_code,
            ownership_name, organization_name, address, phone_area_code,
            phone_number, contract_type, organization_type_code,
            organization_type_name, contract_end_date,
            original_contract_start_date
        ) VALUES (
            :dataset_version_id, :business_group_code, :organization_code,
            :ownership_name, :organization_name, :address, :phone_area_code,
            :phone_number, :contract_type, :organization_type_code,
            :organization_type_name, :contract_end_date,
            :original_contract_start_date
        )
        ON CONFLICT (dataset_version_id, organization_code)
        DO UPDATE SET
            business_group_code = EXCLUDED.business_group_code,
            ownership_name = EXCLUDED.ownership_name,
            organization_name = EXCLUDED.organization_name,
            address = EXCLUDED.address,
            phone_area_code = EXCLUDED.phone_area_code,
            phone_number = EXCLUDED.phone_number,
            contract_type = EXCLUDED.contract_type,
            organization_type_code = EXCLUDED.organization_type_code,
            organization_type_name = EXCLUDED.organization_type_name,
            contract_end_date = EXCLUDED.contract_end_date,
            original_contract_start_date = EXCLUDED.original_contract_start_date
    """),
    "c": text("""
        INSERT INTO healthcare.nhi_org_specialty (
            dataset_version_id, organization_code, specialty_code
        ) VALUES (
            :dataset_version_id, :organization_code, :specialty_code
        )
        ON CONFLICT (dataset_version_id, organization_code, specialty_code)
        DO NOTHING
    """),
    "f": text("""
        INSERT INTO healthcare.nhi_specialty (
            dataset_version_id, specialty_code, specialty_name
        ) VALUES (
            :dataset_version_id, :specialty_code, :specialty_name
        )
        ON CONFLICT (dataset_version_id, specialty_code)
        DO UPDATE SET specialty_name = EXCLUDED.specialty_name
    """),
    "h": text("""
        INSERT INTO healthcare.nhi_org_service (
            dataset_version_id, organization_code, service_code
        ) VALUES (
            :dataset_version_id, :organization_code, :service_code
        )
        ON CONFLICT (dataset_version_id, organization_code, service_code)
        DO NOTHING
    """),
    "e": text("""
        INSERT INTO healthcare.nhi_service_type (
            dataset_version_id, service_code, service_name
        ) VALUES (
            :dataset_version_id, :service_code, :service_name
        )
        ON CONFLICT (dataset_version_id, service_code)
        DO UPDATE SET service_name = EXCLUDED.service_name
    """),
}


def calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    result = str(value).strip()
    if result.endswith(".0") and result[:-2].isdigit():
        result = result[:-2]
    return result or None


def parse_yyyymmdd(value: Any) -> date | None:
    raw = clean_text(value)
    if raw is None:
        return None
    if len(raw) != 8 or not raw.isdigit():
        raise ValueError(f"Invalid YYYYMMDD date: {value!r}")
    try:
        return datetime.strptime(raw, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid YYYYMMDD date: {value!r}") from exc


def read_source(path: Path, spec: SourceSpec) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
        dtype=object,
        keep_default_na=True,
        low_memory=False,
    )
    missing = [c for c in spec.required_columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"{spec.label}: missing required columns: " + ", ".join(missing)
        )
    return df


def require(value: Any, field: str) -> str:
    result = clean_text(value)
    if result is None:
        raise ValueError(f"Missing {field}")
    return result


def normalize_g(row: pd.Series) -> dict[str, Any]:
    return {
        "dataset_version_id": 4,
        "business_group_code": clean_text(row["分區業務組別代碼"]),
        "organization_code": require(row["醫事機構代碼"], "醫事機構代碼"),
        "ownership_name": clean_text(row["權屬別名稱"]),
        "organization_name": require(row["醫事機構名稱"], "醫事機構名稱"),
        "address": clean_text(row["機構地址"]),
        "phone_area_code": clean_text(row["電話區域號碼"]),
        "phone_number": clean_text(row["電話號碼"]),
        "contract_type": clean_text(row["特約類別"]),
        "organization_type_code": clean_text(row["型態別代碼"]),
        "organization_type_name": clean_text(row["醫事機構種類"]),
        "contract_end_date": parse_yyyymmdd(row["終止合約或歇業日期"]),
        "original_contract_start_date": parse_yyyymmdd(row["原始合約起始日期"]),
    }


def normalize_c(row: pd.Series) -> dict[str, Any]:
    return {
        "dataset_version_id": 5,
        "organization_code": require(row["醫事機構代碼"], "醫事機構代碼"),
        "specialty_code": require(row["診療科別"], "診療科別"),
    }


def normalize_f(row: pd.Series) -> dict[str, Any]:
    return {
        "dataset_version_id": 6,
        "specialty_code": require(row["診療科別"], "診療科別"),
        "specialty_name": require(row["診療科別名稱"], "診療科別名稱"),
    }


def normalize_h(row: pd.Series) -> dict[str, Any]:
    return {
        "dataset_version_id": 7,
        "organization_code": require(row["醫事機構代碼"], "醫事機構代碼"),
        "service_code": require(row["機構服務項目代碼"], "機構服務項目代碼"),
    }


def normalize_e(row: pd.Series) -> dict[str, Any]:
    return {
        "dataset_version_id": 8,
        "service_code": require(row["機構服務項目代碼"], "機構服務項目代碼"),
        "service_name": require(row["機構服務項目名稱"], "機構服務項目名稱"),
    }


NORMALIZERS: dict[str, Callable[[pd.Series], dict[str, Any]]] = {
    "g": normalize_g,
    "c": normalize_c,
    "f": normalize_f,
    "h": normalize_h,
    "e": normalize_e,
}


def normalize_rows(
    df: pd.DataFrame,
    spec: SourceSpec,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    normalizer = NORMALIZERS[spec.key]

    for index, row in df.iterrows():
        try:
            normalized.append(normalizer(row))
        except Exception as exc:
            rejected.append({"row_number": int(index) + 2, "error": str(exc)})

    return normalized, rejected


def deduplicate_rows(
    rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
) -> tuple[list[dict[str, Any]], int]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    duplicates = 0
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        result.append(row)
    return result, duplicates


def prepare_source(
    path: Path,
    spec: SourceSpec,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], int]:
    df = read_source(path, spec)
    rows, rejected = normalize_rows(df, spec)
    duplicate_count = 0

    if spec.key == "c":
        rows, duplicate_count = deduplicate_rows(
            rows, ("organization_code", "specialty_code")
        )
    elif spec.key == "h":
        rows, duplicate_count = deduplicate_rows(
            rows, ("organization_code", "service_code")
        )

    return df, rows, rejected, duplicate_count


def upsert_rows(engine, spec: SourceSpec, rows: list[dict[str, Any]]) -> None:
    total = len(rows)
    sql = UPSERT_SQL[spec.key]
    with engine.begin() as conn:
        for start in range(0, total, BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            conn.execute(sql, batch)
            completed = min(start + len(batch), total)
            print(f"  Imported       : {completed:,}/{total:,}")


def print_summary(
    spec: SourceSpec,
    path: Path,
    source_count: int,
    rows: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    duplicate_count: int,
) -> None:
    print()
    print(f"=== {spec.label} ===")
    print(f"Source          : {path}")
    print(f"Version ID      : {spec.dataset_version_id}")
    print(f"Source rows     : {source_count:,}")
    print(f"Normalized rows : {len(rows):,}")
    print(f"Duplicate rows  : {duplicate_count:,}")
    print(f"Rejected rows   : {len(rejected):,}")
    if rows:
        print(f"First row       : {rows[0]}")
    if rejected:
        print("First rejected rows:")
        for item in rejected[:10]:
            print(" ", item)


def import_one(
    *,
    engine,
    path: Path,
    spec: SourceSpec,
    df: pd.DataFrame,
    rows: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    duplicate_count: int,
) -> int:
    if rejected:
        raise RuntimeError(
            f"{spec.label}: import aborted because {len(rejected):,} rows "
            "failed normalization. Run --dry-run and inspect them first."
        )

    checksum = calculate_sha256(path)
    notes = f"Source file: {path.name}"
    if duplicate_count:
        notes += (
            f"; {duplicate_count:,} exact relationship duplicate row(s) "
            "collapsed during normalization"
        )

    batch_id = create_import_batch(
        engine=engine,
        dataset_version_id=spec.dataset_version_id,
        source_checksum=checksum,
        import_program=IMPORT_PROGRAM,
        notes=notes,
    )
    print(f"  Import batch   : {batch_id}")

    try:
        upsert_rows(engine, spec, rows)
        complete_import_batch(
            engine=engine,
            import_batch_id=batch_id,
            source_row_count=len(df),
            imported_row_count=len(rows),
            rejected_row_count=0,
        )
    except Exception as exc:
        fail_import_batch(
            engine=engine,
            import_batch_id=batch_id,
            error_message=str(exc),
        )
        raise

    return batch_id


def resolve(path: Path) -> Path:
    result = path.expanduser().resolve()
    if not result.exists():
        raise FileNotFoundError(f"Source file not found: {result}")
    return result


def run(args: argparse.Namespace) -> None:
    sources = {
        "g": resolve(args.organization),
        "c": resolve(args.org_specialty),
        "f": resolve(args.specialty),
        "h": resolve(args.org_service),
        "e": resolve(args.service_type),
    }

    print("=== HTKD NHI ORGANIZATION FAMILY ===")
    print(f"Environment     : {args.environment}")
    print(f"Dry run         : {args.dry_run}")

    prepared: dict[str, tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], int]] = {}
    for key in ("g", "c", "f", "h", "e"):
        spec = SPECS[key]
        data = prepare_source(sources[key], spec)
        prepared[key] = data
        df, rows, rejected, duplicate_count = data
        print_summary(
            spec, sources[key], len(df), rows, rejected, duplicate_count
        )

    total_rejected = sum(len(data[2]) for data in prepared.values())
    if total_rejected:
        raise RuntimeError(
            f"Dry-run validation found {total_rejected:,} rejected row(s). "
            "No database import should be performed until these are reviewed."
        )

    if args.dry_run:
        print()
        print("Dry run completed. No database rows were changed.")
        return

    engine = get_htkd_engine(args.environment)
    batch_ids: list[int] = []
    for key in ("g", "c", "f", "h", "e"):
        spec = SPECS[key]
        df, rows, rejected, duplicate_count = prepared[key]
        print()
        print(f"Importing {spec.label}...")
        batch_ids.append(
            import_one(
                engine=engine,
                path=sources[key],
                spec=spec,
                df=df,
                rows=rows,
                rejected=rejected,
                duplicate_count=duplicate_count,
            )
        )

    print()
    print("Import completed.")
    print("Import batches   : " + ", ".join(str(x) for x in batch_ids))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import the five Taiwan NHI healthcare-organization files into HTKD."
    )
    parser.add_argument("--organization", type=Path, required=True, help="D2100G CSV")
    parser.add_argument("--org-specialty", type=Path, required=True, help="D2100C CSV")
    parser.add_argument("--specialty", type=Path, required=True, help="D2100F CSV")
    parser.add_argument("--org-service", type=Path, required=True, help="D2100H CSV")
    parser.add_argument("--service-type", type=Path, required=True, help="D2100E CSV")
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()


