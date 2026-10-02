"""Deterministic enterprise design-document extraction for NRI DBA workflows."""

from io import BytesIO

import pandas as pd

def extract_excel_design_document(uploaded_file) -> dict:
    """
    Read an Excel database design document without assuming
    that row 1 contains normalized headers.

    Returns workbook content suitable for LLM interpretation.
    """

    file_bytes = uploaded_file.getvalue()

    excel_file = pd.ExcelFile(
        BytesIO(file_bytes)
    )

    workbook = {
        "file_name": uploaded_file.name,
        "sheets": [],
    }

    for sheet_name in excel_file.sheet_names:

        raw_df = pd.read_excel(
            BytesIO(file_bytes),
            sheet_name=sheet_name,
            header=None,
            dtype=object,
        )

        rows = []

        for row_idx, row in raw_df.iterrows():

            values = []

            for col_idx, value in enumerate(row.tolist()):

                if pd.isna(value):
                    value = ""

                value = str(value).strip()

                values.append({
                    "column_index": int(col_idx + 1),
                    "value": value,
                })

            # skip completely empty rows
            if not any(
                item["value"]
                for item in values
            ):
                continue

            rows.append({
                "row_number": int(row_idx + 1),
                "cells": values,
            })

        workbook["sheets"].append({
            "sheet_name": sheet_name,
            "rows": rows,
        })

    return workbook
