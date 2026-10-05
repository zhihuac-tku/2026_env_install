 # py code beginning

"""Import Taiwan NHI medication reference data into HTKD."""

from __future__ import annotations

import argparse
import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation
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


DATASET_VERSION_ID = 2
IMPORT_PROGRAM = "htkd.importers.tw_nhi_medication"
DEFAULT_ENVIRONMENT = "MacBook"
BATCH_SIZE = 5000

SOURCE_COLUMNS = [
    "異動",
    "藥品代號",
    "藥品英文名稱",
    "藥品中文名稱",
    "成分",
    "規格量",
    "規格單位",
    "單複方",
    "支付價",
    "有效起日",
    "有效迄日",
    "藥商",
    "製造廠名稱",
    "劑型",
    "藥品分類",
    "分類分組名稱",
    "ATC代碼",
    "給付規定章節",
    "藥品代碼超連結",
    "給付規定章節連結",
]


def calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None

    result = str(value).strip()

    if not result or result.lower() == "nan":
        return None

    return result


def parse_decimal(value: Any) -> Decimal | None:
    raw = clean_text(value)

    if raw is None:
        return None

    # NHI source uses "-" when no numeric
    # payment price is provided.
    if raw in {"-", "－", "—"}:
        return None

    raw = raw.replace(",", "")

    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(
            f"Invalid payment price: {value!r}"
        ) from exc


def normalize_roc_date_raw(value: Any) -> str | None:
    raw = clean_text(value)

    if raw is None:
        return None

    # Excel/CSV exports can occasionally make an integer-like value
    # appear as "981001.0".
    if raw.endswith(".0"):
        raw = raw[:-2]

    return raw.strip()


def roc_date_to_gregorian(
    value: Any,
    *,
    allow_open_end: bool = False,
) -> date | None:
    raw = normalize_roc_date_raw(value)

    if raw is None:
        return None

    # NHI uses this as an open-ended/far-future end-date sentinel.
    if allow_open_end and raw == "9991231":
        return None

    if not raw.isdigit():
        raise ValueError(f"Invalid ROC date: {value!r}")

    # ROC date is YYYMMDD, but years before 100 naturally produce
    # six digits (for example 981001 = ROC 98-10-01).
    if len(raw) == 6:
        roc_year = int(raw[:2])
        month = int(raw[2:4])
        day = int(raw[4:6])
    elif len(raw) == 7:
        roc_year = int(raw[:3])
        month = int(raw[3:5])
        day = int(raw[5:7])
    else:
        raise ValueError(
            f"Unexpected ROC date length: {value!r}"
        )

    gregorian_year = roc_year + 1911

    try:
        return date(gregorian_year, month, day)
    except ValueError as exc:
        raise ValueError(
            f"Invalid ROC calendar date: {value!r}"
        ) from exc


def read_source(file_path: Path) -> pd.DataFrame:
    dataframe = pd.read_csv(
        file_path,
        encoding="utf-8-sig",
        dtype=object,
        keep_default_na=True,
        low_memory=False,
    )

    missing_columns = [
        column
        for column in SOURCE_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required source columns: "
            + ", ".join(missing_columns)
        )

    return dataframe


def normalize_row(source_row: pd.Series) -> dict[str, Any]:
    drug_code = clean_text(source_row["藥品代號"])
    effective_start_raw = normalize_roc_date_raw(
        source_row["有效起日"]
    )
    effective_end_raw = normalize_roc_date_raw(
        source_row["有效迄日"]
    )

    if drug_code is None:
        raise ValueError("Missing 藥品代號")

    if effective_start_raw is None:
        raise ValueError(
            f"Missing 有效起日 for drug {drug_code}"
        )

    return {
        "dataset_version_id": DATASET_VERSION_ID,
        "change_type": clean_text(source_row["異動"]),
        "drug_code": drug_code,
        "english_name": clean_text(source_row["藥品英文名稱"]),
        "chinese_name": clean_text(source_row["藥品中文名稱"]),
        "ingredient": clean_text(source_row["成分"]),
        "strength_quantity": clean_text(source_row["規格量"]),
        "strength_unit": clean_text(source_row["規格單位"]),
        "combination_type": clean_text(source_row["單複方"]),
        "payment_price": parse_decimal(source_row["支付價"]),
        "effective_start_raw": effective_start_raw,
        "effective_end_raw": effective_end_raw,
        "effective_start": roc_date_to_gregorian(
            effective_start_raw
        ),
        "effective_end": roc_date_to_gregorian(
            effective_end_raw,
            allow_open_end=True,
        ),
        "pharmaceutical_company": clean_text(source_row["藥商"]),
        "manufacturer_name": clean_text(source_row["製造廠名稱"]),
        "dosage_form": clean_text(source_row["劑型"]),
        "drug_classification": clean_text(source_row["藥品分類"]),
        "classification_group": clean_text(
            source_row["分類分組名稱"]
        ),
        "atc_code": clean_text(source_row["ATC代碼"]),
        "reimbursement_chapter": clean_text(
            source_row["給付規定章節"]
        ),
        "drug_url": clean_text(source_row["藥品代碼超連結"]),
        "reimbursement_url": clean_text(
            source_row["給付規定章節連結"]
        ),
    }


def normalize_rows(
    dataframe: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []

    for row_number, (_, source_row) in enumerate(
        dataframe.iterrows(),
        start=2,
    ):
        try:
            valid_rows.append(normalize_row(source_row))
        except Exception as exc:
            rejected_rows.append(
                {
                    "row_number": row_number,
                    "drug_code": clean_text(
                        source_row.get("藥品代號")
                    ),
                    "error": str(exc),
                }
            )

    return valid_rows, rejected_rows


UPSERT_SQL = text(
    """
    INSERT INTO healthcare.nhi_medication (
        dataset_version_id,
        change_type,
        drug_code,
        english_name,
        chinese_name,
        ingredient,
        strength_quantity,
        strength_unit,
        combination_type,
        payment_price,
        effective_start_raw,
        effective_end_raw,
        effective_start,
        effective_end,
        pharmaceutical_company,
        manufacturer_name,
        dosage_form,
        drug_classification,
        classification_group,
        atc_code,
        reimbursement_chapter,
        drug_url,
        reimbursement_url
    )
    VALUES (
        :dataset_version_id,
        :change_type,
        :drug_code,
        :english_name,
        :chinese_name,
        :ingredient,
        :strength_quantity,
        :strength_unit,
        :combination_type,
        :payment_price,
        :effective_start_raw,
        :effective_end_raw,
        :effective_start,
        :effective_end,
        :pharmaceutical_company,
        :manufacturer_name,
        :dosage_form,
        :drug_classification,
        :classification_group,
        :atc_code,
        :reimbursement_chapter,
        :drug_url,
        :reimbursement_url
    )
    ON CONFLICT (
        dataset_version_id,
        drug_code,
        effective_start_raw
    )
    DO UPDATE SET
        change_type = EXCLUDED.change_type,
        english_name = EXCLUDED.english_name,
        chinese_name = EXCLUDED.chinese_name,
        ingredient = EXCLUDED.ingredient,
        strength_quantity = EXCLUDED.strength_quantity,
        strength_unit = EXCLUDED.strength_unit,
        combination_type = EXCLUDED.combination_type,
        payment_price = EXCLUDED.payment_price,
        effective_end_raw = EXCLUDED.effective_end_raw,
        effective_start = EXCLUDED.effective_start,
        effective_end = EXCLUDED.effective_end,
        pharmaceutical_company = EXCLUDED.pharmaceutical_company,
        manufacturer_name = EXCLUDED.manufacturer_name,
        dosage_form = EXCLUDED.dosage_form,
        drug_classification = EXCLUDED.drug_classification,
        classification_group = EXCLUDED.classification_group,
        atc_code = EXCLUDED.atc_code,
        reimbursement_chapter = EXCLUDED.reimbursement_chapter,
        drug_url = EXCLUDED.drug_url,
        reimbursement_url = EXCLUDED.reimbursement_url
    """
)


def upsert_rows(
    engine: Engine,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = BATCH_SIZE,
) -> int:
    imported = 0

    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            connection.execute(UPSERT_SQL, batch)
            imported += len(batch)

            print(
                f"Imported       : "
                f"{imported:,}/{len(rows):,}"
            )

    return imported


def print_read_only_summary(
    dataframe: pd.DataFrame,
    rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
) -> None:
    print()
    print("=== NHI MEDICATION READ-ONLY CHECK ===")
    print(f"Source rows     : {len(dataframe):,}")
    print(f"Normalized rows : {len(rows):,}")
    print(f"Rejected rows   : {len(rejected_rows):,}")

    print()
    print("=== DATE CONVERSION CHECK ===")
    for raw in ("981001", "1001201", "9991231"):
        converted = roc_date_to_gregorian(
            raw,
            allow_open_end=True,
        )
        print(f"{raw:8} -> {converted}")

    print()
    print("=== FIRST 3 NORMALIZED ROWS ===")
    for row in rows[:3]:
        print(
            {
                "drug_code": row["drug_code"],
                "payment_price": row["payment_price"],
                "effective_start_raw": row[
                    "effective_start_raw"
                ],
                "effective_start": row["effective_start"],
                "effective_end_raw": row[
                    "effective_end_raw"
                ],
                "effective_end": row["effective_end"],
                "atc_code": row["atc_code"],
            }
        )

    if rejected_rows:
        print()
        print("=== FIRST REJECTED ROWS ===")
        for rejected in rejected_rows[:10]:
            print(rejected)


def import_tw_nhi_medication(
    file_path: Path,
    *,
    environment: str = DEFAULT_ENVIRONMENT,
    dry_run: bool = False,
) -> None:
    file_path = file_path.expanduser().resolve()

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    print(f"Source          : {file_path}")
    print(f"Environment     : {environment}")
    print(f"Dataset version : {DATASET_VERSION_ID}")
    print("Reading CSV...")

    dataframe = read_source(file_path)
    rows, rejected_rows = normalize_rows(dataframe)

    if dry_run:
        print_read_only_summary(
            dataframe,
            rows,
            rejected_rows,
        )
        return

    if rejected_rows:
        raise RuntimeError(
            f"Import stopped: "
            f"{len(rejected_rows):,} source rows failed "
            "normalization. Run with --dry-run to inspect them."
        )

    checksum = calculate_sha256(file_path)
    engine = get_htkd_engine(environment)

    print(f"SHA-256         : {checksum}")
    print(f"Source rows     : {len(dataframe):,}")
    print(f"Import rows     : {len(rows):,}")
    print(f"Rejected rows   : {len(rejected_rows):,}")

    import_batch_id = create_import_batch(
        engine,
        dataset_version_id=DATASET_VERSION_ID,
        source_checksum=checksum,
        import_program=IMPORT_PROGRAM,
        notes=f"Source file: {file_path.name}",
    )

    print(f"Import batch    : {import_batch_id}")

    try:
        imported_count = upsert_rows(
            engine,
            rows,
            batch_size=BATCH_SIZE,
        )

        complete_import_batch(
            engine,
            import_batch_id=import_batch_id,
            source_row_count=len(dataframe),
            imported_row_count=imported_count,
            rejected_row_count=len(rejected_rows),
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
            "Import Taiwan NHI medication data into HTKD."
        )
    )
    parser.add_argument(
        "source_file",
        type=Path,
        help="Path to the NHI medication CSV file.",
    )
    parser.add_argument(
        "--environment",
        default=DEFAULT_ENVIRONMENT,
        help="Database environment from nri_code_core.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Read and normalize the source without writing "
            "anything to PostgreSQL."
        ),
    )

    args = parser.parse_args()

    import_tw_nhi_medication(
        args.source_file,
        environment=args.environment,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

