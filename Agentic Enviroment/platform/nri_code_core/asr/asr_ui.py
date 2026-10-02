 # py code beginning

"""Shared ASR interaction UI for NRI / LilyLab applications."""

import streamlit as st

from nri_code_core.asr.asr_runtime import (
    transcribe_audio,
)


# =========================================
# ASR KIOSK STYLE
# =========================================

def apply_asr_kiosk_style() -> None:
    """
    Apply a larger touch target to Streamlit's
    audio recorder for kiosk-style applications.
    """

    st.markdown(
        """
<style>

div[data-testid="stAudioInput"] {
    padding: 20px 24px !important;
    min-height: 110px !important;
    border-radius: 20px !important;
}

div[data-testid="stAudioInput"] button {
    min-width: 72px !important;
    min-height: 72px !important;
    width: 72px !important;
    height: 72px !important;
    border-radius: 50% !important;
}

div[data-testid="stAudioInput"] button svg {
    width: 34px !important;
    height: 34px !important;
}

</style>
""",
        unsafe_allow_html=True,
    )


# =========================================
# ASR INPUT UI
# =========================================

def render_asr_input(
    *,
    asr_option: str,
    key_prefix: str,
    title: str,
    instruction: str,
    recorder_label: str,
    transcript_label: str,
    language: str = "zh",
) -> str:
    """
    Render reusable ASR recording and transcript UI.

    Returns the current editable transcript.
    """

    apply_asr_kiosk_style()

    # -------------------------------------
    # Voice Recording Instruction
    # -------------------------------------

    st.markdown(
        f"""
<div style="
font-size:22px;
font-weight:700;
color:#1b4332;
margin-top:14px;
margin-bottom:8px;
">
{title}
</div>

<div style="
font-size:15px;
color:#6b7280;
margin-bottom:12px;
">
{instruction}
</div>
""",
        unsafe_allow_html=True,
    )

    # -------------------------------------
    # Session-State Keys
    # -------------------------------------

    audio_key = (
        f"{key_prefix}_audio"
    )

    transcript_key = (
        f"{key_prefix}_transcript"
    )

    transcript_editor_key = (
        f"{key_prefix}_transcript_editor"
    )

    signature_key = (
        f"{key_prefix}_last_audio_signature"
    )

    model_key = (
        f"{key_prefix}_last_asr_model"
    )

    # -------------------------------------
    # Large Audio Recorder
    # -------------------------------------

    audio_value = st.audio_input(
        recorder_label,
        key=audio_key,
        label_visibility="collapsed",
    )

    # -------------------------------------
    # Initialize Transcript State
    # -------------------------------------

    if (
        transcript_editor_key
        not in st.session_state
    ):
        st.session_state[
            transcript_editor_key
        ] = ""

    # -------------------------------------
    # Automatic ASR
    # -------------------------------------

    if audio_value:

        audio_bytes = (
            audio_value.getvalue()
        )

        audio_signature = (
            len(audio_bytes),
            hash(audio_bytes),
            asr_option,
        )

        last_audio_signature = (
            st.session_state.get(
                signature_key
            )
        )

        if (
            audio_signature
            != last_audio_signature
        ):

            try:

                with st.spinner(
                    f"🎙️ 正在使用 "
                    f"{asr_option} "
                    "辨識語音……"
                ):

                    transcript = (
                        transcribe_audio(
                            audio_value=audio_value,
                            asr_option=asr_option,
                            language=language,
                        )
                    )

                transcript = (
                    transcript
                    or ""
                ).strip()

                if transcript:

                    st.session_state[
                        transcript_key
                    ] = transcript

                    st.session_state[
                        transcript_editor_key
                    ] = transcript

                    st.session_state[
                        model_key
                    ] = asr_option

                    st.session_state[
                        signature_key
                    ] = (
                        audio_signature
                    )

                    st.success(
                        "✅ 語音辨識完成"
                    )

                    st.rerun()

                else:

                    st.warning(
                        "沒有辨識到有效語音內容。"
                    )

            except Exception as e:

                st.error(
                    "語音辨識失敗："
                    f"{e}"
                )

    # -------------------------------------
    # Transcript Editor
    # -------------------------------------

    transcript_editor = st.text_area(
        transcript_label,
        height=140,
        key=transcript_editor_key,
        placeholder=(
            "完成錄音後，AI 會自動將"
            "語音轉成文字顯示在這裡。"
        ),
    )

    # -------------------------------------
    # ASR Information
    # -------------------------------------

    if transcript_editor.strip():

        last_asr_model = (
            st.session_state.get(
                model_key,
                asr_option,
            )
        )

        st.caption(
            f"🎙️ 辨識模型："
            f"{last_asr_model}"
        )

    return transcript_editor.strip()


