 # py code beginning

"""Reusable result rendering helpers for NRI applications."""

from typing import Any

import pandas as pd
import streamlit as st


# =========================================
# BASIC VALUE HELPERS
# =========================================

def display_value(
    value: Any,
    empty_text: str = "未提供",
) -> str:
    """
    Convert a value into a user-facing string.
    """

    if value is None:
        return empty_text

    if isinstance(
        value,
        str,
    ):
        value = value.strip()

        return (
            value
            if value
            else empty_text
        )

    if isinstance(
        value,
        bool,
    ):
        return (
            "Yes"
            if value
            else "No"
        )

    return str(
        value
    )


# =========================================
# SECTION HEADER
# =========================================

def render_section_header(
    title: str,
    description: str | None = None,
) -> None:
    """
    Render a standard result section header.
    """

    st.markdown(
        f"### {title}"
    )

    if description:

        st.caption(
            description
        )


# =========================================
# KEY / VALUE GRID
# =========================================

def render_key_value_grid(
    items: list[tuple[str, Any]],
    *,
    columns: int = 2,
    empty_text: str = "未提供",
) -> None:
    """
    Render simple key/value information
    using Streamlit metric cards.
    """

    if not items:
        return

    columns = max(
        1,
        int(columns),
    )

    for start in range(
        0,
        len(items),
        columns,
    ):

        row_items = items[
            start:
            start + columns
        ]

        ui_columns = st.columns(
            columns
        )

        for index, (
            label,
            value,
        ) in enumerate(
            row_items
        ):

            with ui_columns[index]:

                st.metric(
                    label,
                    display_value(
                        value,
                        empty_text=empty_text,
                    ),
                )


# =========================================
# LIST SECTION
# =========================================

def render_list_section(
    title: str,
    items: list[Any] | None,
    *,
    empty_text: str = "未提供",
) -> None:
    """
    Render a title followed by a bullet list.

    Use this for information where each item
    should remain an independent row.
    """

    st.markdown(
        f"#### {title}"
    )

    items = items or []

    if not items:

        st.caption(
            empty_text
        )

        return

    for item in items:

        value = display_value(
            item
        )

        st.write(
            f"• {value}"
        )


# =========================================
# INLINE LIST
# =========================================

def render_inline_list(
    items: list[Any] | None,
    *,
    separator: str = "、",
    empty_text: str = "未提供",
) -> None:
    """
    Render short values on one line.

    Example:
        發燒、頭痛、肌肉痠痛
    """

    items = items or []

    if not items:

        st.caption(
            empty_text
        )

        return

    values = [
        display_value(
            item
        )
        for item in items
    ]

    st.write(
        separator.join(
            values
        )
    )


# =========================================
# STATUS MESSAGE
# =========================================

def render_status(
    message: str,
    *,
    status: str = "info",
) -> None:
    """
    Render a standardized status message.

    status:
        success
        warning
        error
        info
    """

    status = (
        status
        .strip()
        .lower()
    )

    if status == "success":

        st.success(
            message
        )

    elif status == "warning":

        st.warning(
            message
        )

    elif status == "error":

        st.error(
            message
        )

    else:

        st.info(
            message
        )


# =========================================
# DICTIONARY TABLE
# =========================================

def render_dict_table(
    data: dict[str, Any] | None,
    *,
    key_label: str = "Field",
    value_label: str = "Value",
) -> None:
    """
    Render a simple dictionary as a table.
    """

    data = data or {}

    if not data:

        st.caption(
            "No data."
        )

        return

    rows = []

    for key, value in data.items():

        rows.append(
            {
                key_label:
                    key,

                value_label:
                    display_value(
                        value
                    ),
            }
        )

    dataframe = pd.DataFrame(
        rows
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )


# =========================================
# RECORD TABLE
# =========================================

def render_record_table(
    records: list[dict[str, Any]] | None,
    *,
    empty_text: str = "No data.",
) -> None:
    """
    Render a list of dictionaries as a
    Streamlit dataframe.
    """

    records = records or []

    if not records:

        st.caption(
            empty_text
        )

        return

    dataframe = pd.DataFrame(
        records
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )


# =========================================
# EVIDENCE BLOCK
# =========================================

def render_evidence_block(
    *,
    title: str,
    source: str | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Generic evidence/result block.

    This function does not know what the
    evidence represents. Domain-specific
    modules decide what values to provide.
    """

    with st.container(
        border=True
    ):

        st.markdown(
            f"#### {title}"
        )

        if source:

            st.caption(
                f"Source: {source}"
            )

        if summary:

            st.write(
                summary
            )

        if metadata:

            render_dict_table(
                metadata
            )


# =========================================
# JSON VIEWER
# =========================================

def render_json_result(
    data: Any,
    *,
    title: str = "完整 JSON",
    expanded: bool = False,
) -> None:
    """
    Render raw structured output in an
    expandable JSON viewer.
    """

    with st.expander(
        title,
        expanded=expanded,
    ):

        st.json(
            data
        )


# =========================================
# RESULT SECTION
# =========================================

def render_result_section(
    *,
    title: str,
    data: Any,
    description: str | None = None,
    expanded: bool = True,
) -> None:
    """
    Generic structured result section.

    Intended as a fallback renderer when a
    domain-specific renderer is unavailable.
    """

    with st.expander(
        title,
        expanded=expanded,
    ):

        if description:

            st.caption(
                description
            )

        if isinstance(
            data,
            dict,
        ):

            render_dict_table(
                data
            )

        elif (
            isinstance(
                data,
                list,
            )
            and data
            and all(
                isinstance(
                    item,
                    dict,
                )
                for item in data
            )
        ):

            render_record_table(
                data
            )

        elif isinstance(
            data,
            list,
        ):

            for item in data:

                st.write(
                    f"• {display_value(item)}"
                )

        elif data is None:

            st.caption(
                "No data."
            )

        else:

            st.write(
                data
            )

