from __future__ import annotations
import pandas as pd
import streamlit as st

def session_default(key, default_value):
    if key not in st.session_state:
        st.session_state[key] = default_value

def safe_sum(df, col):
    if df.empty or col not in df.columns:
        return 0
    return float(df[col].fillna(0).sum())

def safe_nunique(df, col):
    if df.empty or col not in df.columns:
        return 0
    return int(df[col].nunique())

def fmt_number(v):
    if pd.isna(v):
        return "N/A"
    return f"{v:,.0f}"

def fmt_money_thousand(v):
    if pd.isna(v):
        return "N/A"
    return f"{v:,.0f} 千元"
