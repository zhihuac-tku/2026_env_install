 # py code beginning

from __future__ import annotations

import base64
import io
import os
import tempfile

from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from matplotlib import font_manager

from reportlab.platypus import (
    Paragraph,
    Spacer,
    Image as RLImage,
    Table,
    TableStyle,
)

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle,
)

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import (
    UnicodeCIDFont,
)
from reportlab.pdfbase.ttfonts import TTFont


# =============================================================================
# NRI REPORT COLORS
# =============================================================================

NRI_NAVY = "#000F78"
NRI_BLUE_1 = "#96BEF5"
NRI_BLUE_2 = "#0F55C3"
NRI_BLUE_3 = "#64AADC"
NRI_BLUE_4 = "#3C64AA"
NRI_BLUE_5 = "#64A5B4"
NRI_BLUE_GRAY = "#E4ECED"

NRI_CHART_COLORS = [
    NRI_NAVY,
    NRI_BLUE_2,
    NRI_BLUE_4,
    NRI_BLUE_3,
    NRI_BLUE_1,
    NRI_BLUE_5,
    NRI_BLUE_GRAY,
]


# =============================================================================
# CHART STYLE
# =============================================================================

def nri_pdf_chart_style(
    ax,
    title,
    x_label=None,
    y_label=None,
):
    ax.set_title(
        title,
        fontsize=14,
        color=NRI_NAVY,
        fontweight="bold",
        pad=14,
    )

    if x_label:
        ax.set_xlabel(
            x_label,
            fontsize=10,
            color="#333333",
        )

    if y_label:
        ax.set_ylabel(
            y_label,
            fontsize=10,
            color="#333333",
        )

    ax.grid(
        True,
        axis="y",
        color="#E6E6E6",
        linewidth=0.8,
    )

    ax.spines["top"].set_visible(
        False
    )

    ax.spines["right"].set_visible(
        False
    )

    ax.tick_params(
        axis="both",
        labelsize=8,
        colors="#333333",
    )


def nri_pdf_savefig(
    fig,
    tmp_name,
):
    fig.patch.set_facecolor(
        "white"
    )

    plt.tight_layout()

    fig.savefig(
        tmp_name,
        dpi=200,
        bbox_inches="tight",
        facecolor="white",
    )

    plt.close(
        fig
    )


# =============================================================================
# PDF FONTS
# =============================================================================

def nri_register_pdf_fonts():
    font_regular = "NRI_TC"
    font_bold = "NRI_TC_Bold"

    regular_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/NotoSansTC-Regular.otf",
        "/Library/Fonts/Microsoft JhengHei.ttf",
    ]

    bold_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/NotoSansTC-Bold.otf",
        "/Library/Fonts/Microsoft JhengHei Bold.ttf",
    ]

    try:
        regular_path = next(
            path
            for path in regular_paths
            if os.path.exists(
                path
            )
        )

        bold_path = next(
            (
                path
                for path in bold_paths
                if os.path.exists(
                    path
                )
            ),
            regular_path,
        )

        pdfmetrics.registerFont(
            TTFont(
                font_regular,
                regular_path,
            )
        )

        pdfmetrics.registerFont(
            TTFont(
                font_bold,
                bold_path,
            )
        )

        return (
            font_regular,
            font_bold,
        )

    except Exception:
        pdfmetrics.registerFont(
            UnicodeCIDFont(
                "STSong-Light"
            )
        )

        return (
            "STSong-Light",
            "STSong-Light",
        )


# =============================================================================
# PDF TEXT STYLES
# =============================================================================

def nri_pdf_text_styles():
    (
        font_regular,
        font_bold,
    ) = nri_register_pdf_fonts()

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="NRI_Title",
            fontName=font_bold,
            fontSize=20,
            leading=26,
            textColor=colors.HexColor(
                NRI_NAVY
            ),
            spaceAfter=14,
        )
    )

    styles.add(
        ParagraphStyle(
            name="NRI_Body",
            fontName=font_regular,
            fontSize=12,
            leading=22,
            textColor=colors.HexColor(
                "#333333"
            ),
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="NRI_H2",
            fontName=font_bold,
            fontSize=16,
            leading=20,
            textColor=colors.HexColor(
                NRI_NAVY
            ),
            spaceBefore=10,
            spaceAfter=6,
        )
    )

    styles.add(
        ParagraphStyle(
            name="NRI_H3",
            fontName=font_regular,
            fontSize=14,
            leading=20,
            textColor=colors.HexColor(
                "#333333"
            ),
            spaceBefore=8,
            spaceAfter=5,
        )
    )

    styles.add(
        ParagraphStyle(
            name="NRI_H4",
            fontName=font_regular,
            fontSize=12,
            leading=17,
            textColor=colors.HexColor(
                "#333333"
            ),
            spaceBefore=6,
            spaceAfter=4,
        )
    )

    styles.add(
        ParagraphStyle(
            name="NRI_H5",
            fontName=font_regular,
            fontSize=12,
            leading=17,
            textColor=colors.HexColor(
                "#666666"
            ),
            spaceBefore=4,
            spaceAfter=3,
        )
    )

    return styles


# =============================================================================
# MATPLOTLIB FONT
# =============================================================================

def setup_nri_matplotlib_font():
    candidates = [
        "Microsoft JhengHei",
        "Arial Unicode MS",
        "PingFang TC",
        "Heiti TC",
        "Hiragino Sans",
        "Noto Sans CJK TC",
    ]

    available_fonts = {
        font.name
        for font
        in font_manager.fontManager.ttflist
    }

    for font_name in candidates:
        if font_name in available_fonts:
            plt.rcParams[
                "font.family"
            ] = font_name

            plt.rcParams[
                "axes.unicode_minus"
            ] = False

            return font_name

    plt.rcParams[
        "font.family"
    ] = "DejaVu Sans"

    plt.rcParams[
        "axes.unicode_minus"
    ] = False

    return "DejaVu Sans"


# =============================================================================
# PDF FOOTER
# =============================================================================

def nri_pdf_footer(
    canvas,
    doc,
):
    canvas.saveState()

    (
        font_regular,
        _,
    ) = nri_register_pdf_fonts()

    document_date = (
        date.today().strftime(
            "%Y-%m-%d"
        )
    )

    page_width, _ = A4

    footer_y = 24
    line_y = 38

    canvas.setStrokeColor(
        colors.HexColor(
            NRI_NAVY
        )
    )

    canvas.setLineWidth(
        0.6
    )

    canvas.line(
        doc.leftMargin,
        line_y,
        page_width - doc.rightMargin,
        line_y,
    )

    canvas.setFont(
        font_regular,
        9,
    )

    canvas.setFillColor(
        colors.HexColor(
            "#666666"
        )
    )

    canvas.drawString(
        doc.leftMargin,
        footer_y,
        (
            "NRI Taiwan | "
            f"Document Date: {document_date}"
        ),
    )

    canvas.drawRightString(
        page_width - doc.rightMargin,
        footer_y,
        f"Page {doc.page}",
    )

    canvas.restoreState()


# =============================================================================
# PDF TABLE
# =============================================================================

def nri_pdf_table(
    data,
    col_widths=None,
    right_align_cols=None,
    center_align_cols=None,
):
    right_align_cols = (
        right_align_cols
        or []
    )

    center_align_cols = (
        center_align_cols
        or []
    )

    (
        font_regular,
        font_bold,
    ) = nri_register_pdf_fonts()

    table = Table(
        data,
        colWidths=col_widths,
        hAlign="LEFT",
        repeatRows=1,
    )

    style = TableStyle(
        [
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor(
                    NRI_NAVY
                ),
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white,
            ),

            # Header font
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                font_bold,
            ),

            # Body font
            (
                "FONTNAME",
                (0, 1),
                (-1, -1),
                font_regular,
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                9,
            ),
            (
                "LEADING",
                (0, 0),
                (-1, -1),
                14,
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor(
                    "#D9DDE5"
                ),
            ),
            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                colors.HexColor(
                    "#F8F9FB"
                ),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, 0),
                "CENTER",
            ),
            (
                "ALIGN",
                (0, 1),
                (-1, -1),
                "LEFT",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5,
            ),
        ]
    )

    for col in right_align_cols:
        style.add(
            "ALIGN",
            (col, 1),
            (col, -1),
            "RIGHT",
        )

    for col in center_align_cols:
        style.add(
            "ALIGN",
            (col, 1),
            (col, -1),
            "CENTER",
        )

    table.setStyle(
        style
    )

    return table


# =============================================================================
# SAVED REPORT INPUTS
# =============================================================================

def show_saved_report_inputs(
    report_inputs,
    input_sections,
):
    st.markdown(
        "### 📦 Saved Report Inputs"
    )

    if not report_inputs:
        st.warning(
            "No saved inputs yet. "
            "Please save context from "
            "previous tabs first."
        )
        return

    for title, key in input_sections:
        with st.expander(
            title,
            expanded=True,
        ):
            value = report_inputs.get(
                key
            )

            if value:
                st.json(
                    value
                )

            else:
                st.info(
                    f"{key} not saved yet."
                )


# =============================================================================
# AI REPORT CONTEXT
# =============================================================================

def show_ai_report_context(
    report_context,
    title=(
        "View final JSON context "
        "sent to LLM"
    ),
):
    with st.expander(
        title,
        expanded=False,
    ):
        st.json(
            report_context
        )


# =============================================================================
# AI INSTRUCTION BOX
# =============================================================================
#
# NOTE:
# Kept temporarily for compatibility with other applications.
# The DBA Design Review application no longer needs to use the
# old Copilot concept.
# =============================================================================

def ai_copilot_instruction_box(
    key,
    default_instruction,
    height=180,
):
    instruction = st.text_area(
        (
            "Optional user instruction / "
            "使用者補充指示（選填）"
        ),
        value=st.session_state.get(
            key,
            default_instruction,
        ),
        height=height,
    )

    st.session_state[
        key
    ] = instruction

    return instruction


# =============================================================================
# PDF PREVIEW
# =============================================================================

def show_pdf_preview(
    pdf_buffer,
    height=800,
):
    pdf_bytes = (
        pdf_buffer.getvalue()
    )

    b64_pdf = (
        base64.b64encode(
            pdf_bytes
        ).decode(
            "utf-8"
        )
    )

    st.markdown(
        f"""
        <iframe
            src="data:application/pdf;base64,{b64_pdf}"
            width="100%"
            height="{height}"
            type="application/pdf">
        </iframe>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# AI REPORT PDF DOWNLOAD
# =============================================================================

def show_ai_report_pdf_download(
    report_text,
    report_context,
    pdf_builder_func,
    file_name,
    title="### 📝 Generated AI Report",
    button_label=(
        "⬇️ Download AI Report PDF"
    ),
):
    if not report_text:
        return

    st.markdown(
        title
    )

    pdf_buffer = (
        pdf_builder_func(
            report_context=report_context,
            report_text=report_text,
        )
    )

    show_pdf_preview(
        pdf_buffer,
        height=900,
    )

    st.download_button(
        button_label,
        data=pdf_buffer.getvalue(),
        file_name=file_name,
        mime="application/pdf",
        use_container_width=True,
    )

