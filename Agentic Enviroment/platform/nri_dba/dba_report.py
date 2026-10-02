 # py code beginning

from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


# =============================================================================
# REPORT RUNTIME
# =============================================================================

_NRI_PDF_TABLE = None
_NRI_PDF_TEXT_STYLES = None
_NRI_PDF_FOOTER = None
_BUILD_LLM_GENERATION_METADATA = None


def configure_report_runtime(
    *,
    nri_pdf_table,
    nri_pdf_text_styles,
    nri_pdf_footer,
    build_llm_generation_metadata,
):
    """
    Configure shared NRI report infrastructure.

    This module renders already-produced structured Agent output.
    It does not perform DBA reasoning or database investigation.
    """

    global _NRI_PDF_TABLE
    global _NRI_PDF_TEXT_STYLES
    global _NRI_PDF_FOOTER
    global _BUILD_LLM_GENERATION_METADATA

    _NRI_PDF_TABLE = nri_pdf_table
    _NRI_PDF_TEXT_STYLES = nri_pdf_text_styles
    _NRI_PDF_FOOTER = nri_pdf_footer
    _BUILD_LLM_GENERATION_METADATA = (
        build_llm_generation_metadata
    )


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _require_runtime():
    if (
        _NRI_PDF_TABLE is None
        or _NRI_PDF_TEXT_STYLES is None
        or _NRI_PDF_FOOTER is None
        or _BUILD_LLM_GENERATION_METADATA is None
    ):
        raise RuntimeError(
            "DBA report runtime has not been configured. "
            "Call configure_report_runtime() first."
        )


def _safe_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    if isinstance(
        value,
        bool,
    ):
        return "Yes" if value else "No"

    return str(
        value
    ).strip()


def _paragraph_text(
    value: Any,
) -> str:
    """
    Convert arbitrary text to safe ReportLab paragraph text.
    """

    text = _safe_text(
        value
    )

    if not text:
        return ""

    return escape(
        text
    ).replace(
        "\n",
        "<br/>",
    )


def _label(
    key: Any,
) -> str:
    """
    Convert structured field names into readable report labels.
    """

    text = _safe_text(
        key
    ).replace(
        "_",
        " ",
    )

    if not text:
        return ""

    return (
        text[:1].upper()
        + text[1:]
    )


def _simple_value(
    value: Any,
) -> bool:
    return not isinstance(
        value,
        (
            dict,
            list,
            tuple,
        ),
    )


def _add_heading(
    story: list,
    text: str,
    styles,
    *,
    level: int = 2,
):
    style_name = {
        2: "NRI_H2",
        3: "NRI_H3",
        4: "NRI_H4",
        5: "NRI_H5",
    }.get(
        level,
        "NRI_H3",
    )

    story.append(
        Paragraph(
            _paragraph_text(
                text
            ),
            styles[
                style_name
            ],
        )
    )


def _add_body(
    story: list,
    value: Any,
    styles,
):
    text = _paragraph_text(
        value
    )

    if not text:
        return

    story.append(
        Paragraph(
            text,
            styles[
                "NRI_Body"
            ],
        )
    )


def _render_mapping_table(
    story: list,
    mapping: dict,
    styles,
):
    """
    Render scalar dictionary fields as a two-column table.
    """

    rows = [
        [
            "Field",
            "Value",
        ]
    ]

    for key, value in mapping.items():
        if not _simple_value(
            value
        ):
            continue

        rows.append(
            [
                Paragraph(
                    _paragraph_text(
                        _label(
                            key
                        )
                    ),
                    styles[
                        "NRI_Body"
                    ],
                ),
                Paragraph(
                    (
                        _paragraph_text(
                            value
                        )
                        or "-"
                    ),
                    styles[
                        "NRI_Body"
                    ],
                ),
            ]
        )

    if len(
        rows
    ) <= 1:
        return

    story.append(
        _NRI_PDF_TABLE(
            rows,
            col_widths=[
                52 * mm,
                118 * mm,
            ],
        )
    )

    story.append(
        Spacer(
            1,
            8,
        )
    )


def _render_list_of_mappings(
    story: list,
    values: list,
    styles,
) -> bool:
    """
    Render list[dict] as a PDF table only when the content is
    genuinely compact and tabular.

    Long Agent-generated narrative content must remain as
    separate report blocks so ReportLab can split it across pages.
    """

    records = [
        item
        for item in values
        if isinstance(
            item,
            dict,
        )
    ]

    if not records:
        return False

    if len(records) != len(values):
        return False

    keys = []

    for record in records:
        for key in record:
            if key not in keys:
                keys.append(
                    key
                )

    if not keys:
        return False

    # Wide structures are not suitable for a PDF table.
    if len(keys) > 6:
        return False

    # ---------------------------------------------------------
    # TABLE-SAFETY CHECK
    # ---------------------------------------------------------
    # Agent output can contain long narrative fields such as:
    # heading, content, finding, recommendation, evidence, etc.
    #
    # A ReportLab table row cannot split a very tall cell safely
    # across pages. Therefore only compact records are rendered
    # as tables.
    # ---------------------------------------------------------

    max_cell_characters = 300
    max_record_characters = 900

    for record in records:
        record_characters = 0

        for key in keys:
            value = record.get(
                key,
                "",
            )

            # Nested structures are not compact table cells.
            if isinstance(
                value,
                (
                    dict,
                    list,
                    tuple,
                ),
            ):
                return False

            text = _safe_text(
                value
            )

            record_characters += len(
                text
            )

            if len(text) > max_cell_characters:
                return False

        if record_characters > max_record_characters:
            return False

    # ---------------------------------------------------------
    # COMPACT TABULAR CONTENT
    # ---------------------------------------------------------

    rows = [
        [
            Paragraph(
                _paragraph_text(
                    _label(
                        key
                    )
                ),
                styles[
                    "NRI_Body"
                ],
            )
            for key in keys
        ]
    ]

    for record in records:
        rows.append(
            [
                Paragraph(
                    (
                        _paragraph_text(
                            record.get(
                                key,
                                "",
                            )
                        )
                        or "-"
                    ),
                    styles[
                        "NRI_Body"
                    ],
                )
                for key in keys
            ]
        )

    usable_width = (
        170 * mm
    )

    col_width = (
        usable_width
        / len(keys)
    )

    story.append(
        _NRI_PDF_TABLE(
            rows,
            col_widths=[
                col_width
                for _ in keys
            ],
        )
    )

    story.append(
        Spacer(
            1,
            8,
        )
    )

    return True


def _render_value(
    story: list,
    key: str,
    value: Any,
    styles,
    *,
    level: int = 2,
):
    """
    Render structured Agent output.

    This function performs presentation only.
    It does not make DBA decisions.
    """

    title = _label(
        key
    )

    # -----------------------------------------------------------------
    # Dictionary
    # -----------------------------------------------------------------

    if isinstance(
        value,
        dict,
    ):
        if title:
            _add_heading(
                story,
                title,
                styles,
                level=level,
            )

        _render_mapping_table(
            story,
            value,
            styles,
        )

        for (
            child_key,
            child_value,
        ) in value.items():
            if _simple_value(
                child_value
            ):
                continue

            _render_value(
                story,
                child_key,
                child_value,
                styles,
                level=min(
                    level + 1,
                    5,
                ),
            )

        return

    # -----------------------------------------------------------------
    # List / tuple
    # -----------------------------------------------------------------

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        if title:
            _add_heading(
                story,
                title,
                styles,
                level=level,
            )

        values = list(
            value
        )

        if not values:
            _add_body(
                story,
                "No items.",
                styles,
            )
            return

        if _render_list_of_mappings(
            story,
            values,
            styles,
        ):
            return

        for (
            index,
            item,
        ) in enumerate(
            values,
            start=1,
        ):
            if isinstance(
                item,
                dict,
            ):
                _add_heading(
                    story,
                    f"Item {index}",
                    styles,
                    level=min(
                        level + 1,
                        5,
                    ),
                )

                _render_mapping_table(
                    story,
                    item,
                    styles,
                )

                for (
                    child_key,
                    child_value,
                ) in item.items():
                    if _simple_value(
                        child_value
                    ):
                        continue

                    _render_value(
                        story,
                        child_key,
                        child_value,
                        styles,
                        level=min(
                            level + 2,
                            5,
                        ),
                    )

            else:
                _add_body(
                    story,
                    (
                        "• "
                        + _safe_text(
                            item
                        )
                    ),
                    styles,
                )

        return

    # -----------------------------------------------------------------
    # Scalar
    # -----------------------------------------------------------------

    if title:
        _add_heading(
            story,
            title,
            styles,
            level=level,
        )

    _add_body(
        story,
        value,
        styles,
    )


def _build_metadata_section(
    story: list,
    *,
    llm_cfg: dict,
    styles,
):
    metadata = (
        _BUILD_LLM_GENERATION_METADATA(
            llm_cfg
        )
        or {}
    )

    if not metadata:
        return

    _add_heading(
        story,
        "Generation Metadata",
        styles,
        level=2,
    )

    _render_mapping_table(
        story,
        metadata,
        styles,
    )


def _build_structured_pdf(
    *,
    title: str,
    structured_content: dict,
    llm_cfg: dict,
    context_summary: dict | None = None,
) -> BytesIO:
    """
    Render structured report content into a PDF.

    Agent reasoning happens before this function.
    This function is presentation only.
    """

    _require_runtime()

    styles = (
        _NRI_PDF_TEXT_STYLES()
    )

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=title,
    )

    story = []

    story.append(
        Paragraph(
            _paragraph_text(
                title
            ),
            styles[
                "NRI_Title"
            ],
        )
    )

    story.append(
        Spacer(
            1,
            8,
        )
    )

    # -----------------------------------------------------------------
    # Report context
    # -----------------------------------------------------------------

    if context_summary:
        _add_heading(
            story,
            "Report Context",
            styles,
            level=2,
        )

        _render_mapping_table(
            story,
            context_summary,
            styles,
        )

    # -----------------------------------------------------------------
    # LLM generation metadata
    # -----------------------------------------------------------------

    _build_metadata_section(
        story,
        llm_cfg=llm_cfg,
        styles=styles,
    )

    # -----------------------------------------------------------------
    # Structured Agent output
    # -----------------------------------------------------------------

    for (
        key,
        value,
    ) in (
        structured_content
        or {}
    ).items():
        _render_value(
            story,
            key,
            value,
            styles,
            level=2,
        )

    doc.build(
        story,
        onFirstPage=(
            _NRI_PDF_FOOTER
        ),
        onLaterPages=(
            _NRI_PDF_FOOTER
        ),
    )

    buffer.seek(
        0
    )

    return buffer


# =============================================================================
# BUSINESS CONSISTENCY REPORT
# =============================================================================

def build_business_consistency_pdf(
    *,
    report_json: dict,
    report_context: dict,
    llm_cfg: dict,
) -> BytesIO:
    """
    Render validated Business Consistency Agent output.
    """

    context_summary = {}

    if isinstance(
        report_context,
        dict,
    ):
        for key in (
            "source_db",
            "schema_name",
            "table_name",
        ):
            if key in report_context:
                context_summary[
                    key
                ] = report_context[
                    key
                ]

    return _build_structured_pdf(
        title=(
            "NRI Business Consistency Report"
        ),
        structured_content=(
            report_json
            or {}
        ),
        context_summary=(
            context_summary
        ),
        llm_cfg=llm_cfg,
    )


# =============================================================================
# AI DATA DICTIONARY REPORT
# =============================================================================

def build_ai_data_dictionary_pdf(
    *,
    report_json: dict,
    report_context: dict,
    llm_cfg: dict,
) -> BytesIO:
    """
    Render validated AI Data Dictionary Agent output.
    """

    context_summary = {}

    if isinstance(
        report_context,
        dict,
    ):
        for key in (
            "source_db",
            "schema_name",
            "table_name",
        ):
            if key in report_context:
                context_summary[
                    key
                ] = report_context[
                    key
                ]

    return _build_structured_pdf(
        title=(
            "NRI AI Data Dictionary Report"
        ),
        structured_content=(
            report_json
            or {}
        ),
        context_summary=(
            context_summary
        ),
        llm_cfg=llm_cfg,
    )


# =============================================================================
# DBA DESIGN REVIEW REPORT
# =============================================================================

def build_dba_review_report_pdf(
    *,
    target_db: str,
    design_obj: dict,
    report_obj: dict,
    llm_cfg: dict,
) -> BytesIO:
    """
    Render structured DBA Design Review report output.
    """

    context_summary = {
        "target_database": (
            target_db
        ),
    }

    if isinstance(
        design_obj,
        dict,
    ):
        schema_name = (
            design_obj.get(
                "schema_name",
                "",
            )
        )

        table_name = (
            design_obj.get(
                "table_name",
                "",
            )
        )

        if schema_name:
            context_summary[
                "schema_name"
            ] = schema_name

        if table_name:
            context_summary[
                "table_name"
            ] = table_name

    return _build_structured_pdf(
        title=(
            "NRI Enterprise DBA Design Review"
        ),
        structured_content=(
            report_obj
            or {}
        ),
        context_summary=(
            context_summary
        ),
        llm_cfg=llm_cfg,
    )


