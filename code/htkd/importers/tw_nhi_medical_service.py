 # py code beginning

"""Importer for Taiwan NHI Medical Service and Payment Standard."""

from __future__ import annotations

import argparse
import hashlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

from htkd.db.htkd_db import (
    complete_import_batch,
    create_import_batch,
    fail_import_batch,
    get_htkd_engine,
)

DATASET_VERSION_ID = 3
IMPORT_PROGRAM = "htkd.importers.tw_nhi_medical_service"
DEFAULT_ENVIRONMENT = "MacBook"
BATCH_SIZE = 5000

REQUIRED_COLUMNS = [
    "診療項目代碼",
    "健保支付點數",
    "生效起日",
    "生效迄日",
    "英文項目名稱",
    "中文項目名稱",
    "備註",
]

UPSERT_SQL = text("""
INSERT INTO healthcare.nhi_medical_service (
    dataset_version_id,
    service_code,
    payment_points,
    effective_start_raw,
    effective_end_raw,
    effective_start,
    effective_end,
    english_name,
    chinese_name,
    notes
)
VALUES (
    :dataset_version_id,
    :service_code,
    :payment_points,
    :effective_start_raw,
    :effective_end_raw,
    :effective_start,
    :effective_end,
    :english_name,
    :chinese_name,
    :notes
)
ON CONFLICT (
    dataset_version_id,
    service_code,
    effective_start_raw
)
DO UPDATE SET
    payment_points = EXCLUDED.payment_points,
    effective_end_raw = EXCLUDED.effective_end_raw,
    effective_start = EXCLUDED.effective_start,
    effective_end = EXCLUDED.effective_end,
    english_name = EXCLUDED.english_name,
    chinese_name = EXCLUDED.chinese_name,
    notes = EXCLUDED.notes
""")


def calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None

    value = str(value).strip()
    if not value:
        return None

    return value


def parse_decimal(value: Any) -> Decimal | None:
    raw = clean_text(value)
    if raw is None:
        return None

    if raw in {"-", "－", "—"}:
        return None

    raw = raw.replace(",", "")

    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(
            f"Invalid payment points: {value!r}"
        ) from exc


def normalize_date_raw(value: Any) -> str | None:
    raw = clean_text(value)
    if raw is None:
        return None

    # Protect against spreadsheet-like values such as 20210301.0.
    if raw.endswith(".0"):
        raw = raw[:-2]

    return raw


def gregorian_date_from_raw(
    value: Any,
    *,
    allow_open_end: bool = False,
) -> date | None:
    raw = normalize_date_raw(value)

    if raw is None:
        return None

    # NHI uses 29101231 as a practical open-ended date.
    if allow_open_end and raw == "29101231":
        return None

    if len(raw) != 8 or not raw.isdigit():
        raise ValueError(
            f"Invalid Gregorian date: {value!r}"
        )

    try:
        return datetime.strptime(
            raw,
            "%Y%m%d",
        ).date()
    except ValueError as exc:
        raise ValueError(
            f"Invalid Gregorian date: {value!r}"
        ) from exc


def read_source(file_path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        file_path,
        encoding="utf-8-sig",
        dtype=object,
        keep_default_na=True,
        low_memory=False,
    )

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing required source columns: "
            + ", ".join(missing)
        )

    return df


def normalize_row(row: pd.Series) -> dict[str, Any]:
    service_code = clean_text(
        row["診療項目代碼"]
    )
    payment_points = parse_decimal(
        row["健保支付點數"]
    )
    effective_start_raw = normalize_date_raw(
        row["生效起日"]
    )
    effective_end_raw = normalize_date_raw(
        row["生效迄日"]
    )
    chinese_name = clean_text(
        row["中文項目名稱"]
    )

    if service_code is None:
        raise ValueError(
            "Missing 診療項目代碼"
        )

    if payment_points is None:
        raise ValueError(
            "Missing 健保支付點數"
        )

    if effective_start_raw is None:
        raise ValueError(
            "Missing 生效起日"
        )

    if chinese_name is None:
        raise ValueError(
            "Missing 中文項目名稱"
        )

    return {
        "dataset_version_id": DATASET_VERSION_ID,
        "service_code": service_code,
        "payment_points": payment_points,
        "effective_start_raw": effective_start_raw,
        "effective_end_raw": effective_end_raw,
        "effective_start": gregorian_date_from_raw(
            effective_start_raw
        ),
        "effective_end": gregorian_date_from_raw(
            effective_end_raw,
            allow_open_end=True,
        ),
        "english_name": clean_text(
            row["英文項目名稱"]
        ),
        "chinese_name": chinese_name,
        "notes": clean_text(
            row["備註"]
        ),
    }


def normalize_rows(
    df: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        try:
            normalized.append(
                normalize_row(row)
            )
        except Exception as exc:
            rejected.append(
                {
                    "row_number": int(index) + 2,
                    "service_code": clean_text(
                        row.get("診療項目代碼")
                    ),
                    "error": str(exc),
                }
            )

    return normalized, rejected


def upsert_rows(
    engine,
    rows: list[dict[str, Any]],
) -> None:
    total = len(rows)

    with engine.begin() as conn:
        for start in range(0, total, BATCH_SIZE):
            batch = rows[
                start:start + BATCH_SIZE
            ]
            conn.execute(
                UPSERT_SQL,
                batch,
            )

            completed = min(
                start + len(batch),
                total,
            )
            print(
                f"Imported       : "
                f"{completed:,}/{total:,}"
            )


def print_read_only_summary(
    *,
    source_rows: int,
    normalized_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
) -> None:
    print()
    print(
        "=== NHI MEDICAL SERVICE "
        "READ-ONLY CHECK ==="
    )
    print(
        f"Source rows     : {source_rows:,}"
    )
    print(
        f"Normalized rows : "
        f"{len(normalized_rows):,}"
    )
    print(
        f"Rejected rows   : "
        f"{len(rejected_rows):,}"
    )

    print()
    print("=== DATE CONVERSION CHECK ===")
    print(
        "20210301 ->",
        gregorian_date_from_raw(
            "20210301"
        ),
    )
    print(
        "29101231 ->",
        gregorian_date_from_raw(
            "29101231",
            allow_open_end=True,
        ),
    )

    print()
    print("=== FIRST 3 NORMALIZED ROWS ===")
    for row in normalized_rows[:3]:
        print(
            {
                "service_code": row[
                    "service_code"
                ],
                "payment_points": row[
                    "payment_points"
                ],
                "effective_start_raw": row[
                    "effective_start_raw"
                ],
                "effective_start": row[
                    "effective_start"
                ],
                "effective_end_raw": row[
                    "effective_end_raw"
                ],
                "effective_end": row[
                    "effective_end"
                ],
            }
        )

    if rejected_rows:
        print()
        print("=== FIRST REJECTED ROWS ===")
        for row in rejected_rows[:10]:
            print(row)


def import_tw_nhi_medical_service(
    *,
    source_path: Path,
    environment: str,
    dry_run: bool,
) -> None:
    source_path = source_path.expanduser().resolve()

    if not source_path.exists():
        raise FileNotFoundError(
            f"Source file not found: "
            f"{source_path}"
        )

    print(f"Source          : {source_path}")
    print(f"Environment     : {environment}")
    print(
        f"Dataset version : "
        f"{DATASET_VERSION_ID}"
    )
    print("Reading CSV...")

    df = read_source(source_path)

    normalized_rows, rejected_rows = (
        normalize_rows(df)
    )

    print_read_only_summary(
        source_rows=len(df),
        normalized_rows=normalized_rows,
        rejected_rows=rejected_rows,
    )

    if dry_run:
        return

    if rejected_rows:
        raise RuntimeError(
            "Import aborted because "
            f"{len(rejected_rows):,} source "
            "rows were rejected. Run with "
            "--dry-run and inspect them first."
        )

    source_checksum = calculate_sha256(
        source_path
    )

    engine = get_htkd_engine(
        environment
    )

    import_batch_id = create_import_batch(
        engine,
        dataset_version_id=DATASET_VERSION_ID,
        source_checksum=source_checksum,
        import_program=IMPORT_PROGRAM,
        notes=f"Source file: {source_path.name}",
    )

    print()
    print(
        f"Import batch   : "
        f"{import_batch_id}"
    )

    try:
        upsert_rows(
            engine,
            normalized_rows,
        )

        complete_import_batch(
            engine=engine,
            import_batch_id=import_batch_id,
            source_row_count=len(df),
            imported_row_count=len(
                normalized_rows
            ),
            rejected_row_count=0,
        )

    except Exception as exc:
        fail_import_batch(
            engine=engine,
            import_batch_id=import_batch_id,
            notes=str(exc),
        )
        raise

    print("Import completed.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import Taiwan NHI Medical "
            "Service and Payment Standard "
            "into HTKD."
        )
    )

    parser.add_argument(
        "source_path",
        type=Path,
    )

    parser.add_argument(
        "--environment",
        default=DEFAULT_ENVIRONMENT,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    return parser


def main() -> None:
    args = build_parser().parse_args()

    import_tw_nhi_medical_service(
        source_path=args.source_path,
        environment=args.environment,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

