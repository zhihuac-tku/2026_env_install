from __future__ import annotations

import pandas as pd
import streamlit as st
import plotly.express as px

NRI_NAVY = "#000F78"
NRI_BLUE_1 = "#96BEF5"
NRI_BLUE_2 = "#0F55C3"
NRI_BLUE_3 = "#64AADC"
NRI_BLUE_4 = "#3C64AA"
NRI_BLUE_5 = "#64A5B4"
NRI_BLUE_GRAY = "#E4ECED"
NRI_CHART_COLORS = [NRI_NAVY,NRI_BLUE_2,NRI_BLUE_4,NRI_BLUE_3,NRI_BLUE_1,NRI_BLUE_5,NRI_BLUE_GRAY]
NRI_CSS = f"""
<style>
h1, h2, h3, h4 {{ color: {NRI_NAVY}; }}
[data-testid="metric-container"] {{ background-color: #F7F8FA; border: 1px solid #D9DDE5; border-radius: 8px; padding: 10px; }}
tbody tr:nth-child(even) {{ background-color: #F8F9FB; }}
</style>
"""

def apply_nri_style():
    st.markdown(NRI_CSS, unsafe_allow_html=True)

def show_sidebar_branding():
    st.sidebar.markdown("NRI TAIWAN")

    with st.sidebar.expander("About", expanded=False):
        st.info("""
This dashboard is for NRI internal industry analysis.

For Users:
- NRI consultants and analysts
- Internal industry research users

""")

def nri_table(df, int_cols=None, decimal_cols=None, percent_cols=None):
    display_df = df.copy()
    column_config = {}

    if int_cols:
        for col in int_cols:
            if col in display_df.columns:
                column_config[col] = st.column_config.NumberColumn(
                    col,
                    format="%,d",
                )

    if decimal_cols:
        for col in decimal_cols:
            if col in display_df.columns:
                column_config[col] = st.column_config.NumberColumn(
                    col,
                    format="%.2f",
                )

    if percent_cols:
        for col in percent_cols:
            if col in display_df.columns:
                column_config[col] = st.column_config.NumberColumn(
                    col,
                    format="%.2%",
                )

    st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=True,
        column_config=column_config,
    )

def nri_line_chart(
    df,
    x_col,
    y_col,
    color_col,
    title,
    y_axis_title="Value",
    color_palette=None,
):
    fig = px.line(
        df,
        x=x_col,
        y=y_col,
        color=color_col,
        color_discrete_sequence=NRI_CHART_COLORS,
        markers=False,
        title=title,
    )

    fig.update_layout(
        template="plotly_white",
        height=420,
        title=dict(
            text=title,
            font=dict(size=20, color="#002060"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.35,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=40, r=20, t=60, b=90),
        xaxis=dict(
            showgrid=False,
            title=None,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#E6E6E6",
            title=y_axis_title,
            tickformat=",",
        ),
        font=dict(
            family="Arial",
            size=12,
            color="#333333",
        ),
    )

    fig.update_traces(
        line=dict(width=4)
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

# ============================================================
# SESSION STATE HELPERS
# ============================================================

def session_default(
    key,
    default_value,
):
    """
    Initialize a Streamlit session-state value only when
    the key does not already exist.
    """

    if key not in st.session_state:
        st.session_state[key] = default_value

    return st.session_state[key]


# ============================================================
# NRI AI COPILOT UI
# ============================================================

def ai_copilot_instruction_box(
    key,
    default_instruction,
    height=180,
):
    """
    Shared NRI AI Copilot instruction input box.
    """

    session_default(
        key,
        default_instruction,
    )

    instruction = st.text_area(
        "Optional user instruction / 使用者補充指示（選填）",
        value=st.session_state.get(
            key,
            default_instruction,
        ),
        height=height,
        key=f"text_area_{key}",
    )

    st.session_state[key] = instruction

    return instruction

