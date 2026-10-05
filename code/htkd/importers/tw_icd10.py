 # py code beginning


"""Importer for Taiwan NHI ICD-10-CM / ICD-10-PCS into HTKD."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Engine, text

from htkd.db.htkd_db import (
    complete_import_batch,
    create_import_batch,
    fail_import_batch,
    get_htkd_engine,
)


DATASET_VERSION_ID = 1
CM_SHEET = "ICD-10-CM"
PCS_SHEET = "ICD-10-PCS"
IMPORT_PROGRAM = "htkd.importers.tw_icd10"


def calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as source:
        for block in iter(
            lambda: source.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def clean_value(value: Any) -> str | None:
    if pd.isna(value):
        return None

    text_value = str(value).strip()

    return text_value or None


def parse_date(value: Any):
    if pd.isna(value):
        return None

    parsed = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(parsed):
        return None

    return parsed.date()


def read_icd_sheet(
    file_path: Path,
    sheet_name: str,
) -> pd.DataFrame:
    """
    Read one of the two main ICD sheets from the
    Taiwan NHI ODS workbook.
    """
    dataframe = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        engine="odf",
        header=0,
        dtype=object,
    )

    return (
        dataframe
        .dropna(how="all")
        .reset_index(drop=True)
    )


def normalize_rows(
    dataframe: pd.DataFrame,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    rejected = 0

    for _, source_row in dataframe.iterrows():
        values = source_row.tolist()

        if len(values) < 6:
            rejected += 1
            continue

        code = clean_value(values[0])

        if not code:
            rejected += 1
            continue

        rows.append(
            {
                "dataset_version_id": DATASET_VERSION_ID,
                "code": code,
                "use_flag": clean_value(values[1]),
                "english_name": clean_value(values[2]),
                "chinese_name": clean_value(values[3]),
                "status": clean_value(values[4]),
                "revision_date": parse_date(values[5]),
            }
        )

    return rows, rejected


def upsert_rows(
    engine: Engine,
    *,
    table_name: str,
    rows: list[dict[str, Any]],
) -> None:
    if table_name not in {
        "icd10_cm",
        "icd10_pcs",
    }:
        raise ValueError(
            f"Unsupported ICD table: {table_name}"
        )

    if not rows:
        return

    sql = text(f"""
        INSERT INTO healthcare.{table_name} (
            dataset_version_id,
            code,
            use_flag,
            english_name,
            chinese_name,
            status,
            revision_date
        )
        VALUES (
            :dataset_version_id,
            :code,
            :use_flag,
            :english_name,
            :chinese_name,
            :status,
            :revision_date
        )
        ON CONFLICT (
            dataset_version_id,
            code
        )
        DO UPDATE SET
            use_flag = EXCLUDED.use_flag,
            english_name = EXCLUDED.english_name,
            chinese_name = EXCLUDED.chinese_name,
            status = EXCLUDED.status,
            revision_date = EXCLUDED.revision_date
    """)

    with engine.begin() as conn:
        conn.execute(
            sql,
            rows,
        )


def import_tw_icd10(
    file_path: Path,
    *,
    environment: str = "MacBook",
) -> None:
    file_path = file_path.expanduser().resolve()

    if not file_path.exists():
        raise FileNotFoundError(
            f"Source file not found: {file_path}"
        )

    engine = get_htkd_engine(environment)

    checksum = calculate_sha256(file_path)

    print(f"Source         : {file_path}")
    print(f"SHA-256        : {checksum}")
    print(f"Environment    : {environment}")

    print(f"Reading {CM_SHEET}...")
    cm_df = read_icd_sheet(
        file_path,
        CM_SHEET,
    )

    print(f"Reading {PCS_SHEET}...")
    pcs_df = read_icd_sheet(
        file_path,
        PCS_SHEET,
    )

    cm_rows, cm_rejected = normalize_rows(cm_df)
    pcs_rows, pcs_rejected = normalize_rows(pcs_df)

    source_row_count = (
        len(cm_df)
        + len(pcs_df)
    )

    imported_row_count = (
        len(cm_rows)
        + len(pcs_rows)
    )

    rejected_row_count = (
        cm_rejected
        + pcs_rejected
    )

    print(f"CM source rows : {len(cm_df):,}")
    print(f"CM import rows : {len(cm_rows):,}")
    print(f"PCS source rows: {len(pcs_df):,}")
    print(f"PCS import rows: {len(pcs_rows):,}")
    print(f"Rejected rows  : {rejected_row_count:,}")

    import_batch_id = create_import_batch(
        engine,
        dataset_version_id=DATASET_VERSION_ID,
        source_checksum=checksum,
        import_program=IMPORT_PROGRAM,
        notes=f"Source file: {file_path.name}",
    )

    print(f"Import batch   : {import_batch_id}")

    try:
        upsert_rows(
            engine,
            table_name="icd10_cm",
            rows=cm_rows,
        )

        upsert_rows(
            engine,
            table_name="icd10_pcs",
            rows=pcs_rows,
        )

        complete_import_batch(
            engine,
            import_batch_id=import_batch_id,
            source_row_count=source_row_count,
            imported_row_count=imported_row_count,
            rejected_row_count=rejected_row_count,
        )

    except Exception as exc:
        fail_import_batch(
            engine,
            import_batch_id=import_batch_id,
            error_message=str(exc),
        )
        raise

    print("Import completed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import Taiwan NHI ICD-10-CM/PCS ODS "
            "into HTKD."
        )
    )

    parser.add_argument(
        "source_file",
        type=Path,
        help="Path to the NHI ICD-10-CM/PCS ODS file.",
    )

    parser.add_argument(
        "--environment",
        default="MacBook",
        choices=[
            "MacBook",
            "iMac",
            "NRI Notebook",
        ],
        help="Database environment from nri_code_core.",
    )

    args = parser.parse_args()

    import_tw_icd10(
        args.source_file,
        environment=args.environment,
    )


if __name__ == "__main__":
    main()


