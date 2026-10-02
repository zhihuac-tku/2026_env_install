 # py code beginning

"""Shared weather runtime for NRI / LilyLab applications."""

import streamlit as st


# =========================================
# WEATHER CONFIGURATION
# =========================================

WEATHER_OPTIONS = {
    "CWA Open Data": {
        "provider": "cwa",
    },
}

DEFAULT_WEATHER_OPTION = "CWA Open Data"


# =========================================
# WEATHER SIDEBAR
# =========================================

def select_weather_sidebar() -> dict:
    """
    Render the shared weather runtime
    configuration in the Streamlit sidebar.
    """

    with st.sidebar:
        st.markdown(
            "### 🌤 Weather Data"
        )

        weather_option_names = list(
            WEATHER_OPTIONS.keys()
        )

        selected_weather_option = (
            st.selectbox(
                "Weather Provider",
                options=(
                    weather_option_names
                ),
                index=(
                    weather_option_names.index(
                        DEFAULT_WEATHER_OPTION
                    )
                ),
                key=(
                    "selected_weather_option"
                ),
                help=(
                    "Select the weather data "
                    "provider."
                ),
            )
        )

        weather_config = (
            WEATHER_OPTIONS[
                selected_weather_option
            ]
        )

        provider = (
            weather_config[
                "provider"
            ]
        )

        api_key = st.text_input(
            "CWA API Key",
            type="password",
            key="cwa_api_key",
            help=(
                "中央氣象署氣象資料開放平台 "
                "Authorization Key"
            ),
        )

        enabled = bool(
            api_key.strip()
        )

        if enabled:
            st.success(
                "CWA Weather API 已設定"
            )
        else:
            st.info(
                "尚未設定 CWA API Key"
            )

    return {
        "enabled": enabled,
        "provider": provider,
        "provider_name": (
            selected_weather_option
        ),
        "api_key": api_key.strip(),
    }

