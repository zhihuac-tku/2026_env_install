 # py code beginning

"""Shared ASR runtime for NRI / LilyLab applications."""

import os
import tempfile

import streamlit as st


# =========================================
# ASR CONFIGURATION
# =========================================

ASR_OPTIONS = {
    "Whisper Large-v3": {
        "engine": "faster_whisper",
        "model": "large-v3",
    },
    "Taiwan-Tongues-ASR-CE": {
        "engine": "faster_whisper",
        "model": (
            "adi-gov-tw/"
            "Taiwan-Tongues-ASR-CE-v1.0"
        ),
    },
}

DEFAULT_ASR_OPTION = "Whisper Large-v3"


# =========================================
# OPTIONAL ASR LIBRARIES
# =========================================

try:
    from faster_whisper import WhisperModel

    HAS_FASTER_WHISPER = True

except ImportError:
    WhisperModel = None
    HAS_FASTER_WHISPER = False


# =========================================
# ASR MODEL
# =========================================

@st.cache_resource
def load_whisper_model(
    model_size: str = "small",
):
    if not HAS_FASTER_WHISPER:
        raise RuntimeError(
            "faster-whisper is not installed. "
            "Run: pip install faster-whisper"
        )

    return WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
    )


# =========================================
# FASTER-WHISPER
# =========================================

def transcribe_with_faster_whisper(
    temp_path: str,
    model_name: str,
    language: str,
) -> str:
    model = load_whisper_model(
        model_name
    )

    segments, _ = model.transcribe(
        temp_path,
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    transcript_parts = []

    for segment in segments:
        segment_text = (
            segment.text or ""
        ).strip()

        if segment_text:
            transcript_parts.append(
                segment_text
            )

    return " ".join(
        transcript_parts
    ).strip()


# =========================================
# SHARED TRANSCRIPTION ENTRY
# =========================================

def transcribe_audio(
    audio_value,
    asr_option: str,
    language: str = "zh",
) -> str:
    if audio_value is None:
        return ""

    if asr_option not in ASR_OPTIONS:
        raise ValueError(
            f"Unknown ASR option: {asr_option}"
        )

    audio_bytes = audio_value.getvalue()

    if not audio_bytes:
        raise ValueError(
            "The recorded audio is empty."
        )

    mime_type = getattr(
        audio_value,
        "type",
        "",
    )

    suffix_map = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
    }

    suffix = suffix_map.get(
        mime_type,
        ".wav",
    )

    asr_config = ASR_OPTIONS[
        asr_option
    ]

    engine = asr_config["engine"]
    model_name = asr_config["model"]

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(
                audio_bytes
            )
            temp_path = temp_file.name

        if engine == "faster_whisper":
            transcript = (
                transcribe_with_faster_whisper(
                    temp_path=temp_path,
                    model_name=model_name,
                    language=language,
                )
            )

        else:
            raise ValueError(
                f"Unsupported ASR engine: {engine}"
            )

        transcript = (
            transcript or ""
        ).strip()

        if not transcript:
            raise RuntimeError(
                "No recognizable speech was found."
            )

        return transcript

    finally:
        if (
            temp_path
            and os.path.exists(temp_path)
        ):
            try:
                os.remove(
                    temp_path
                )
            except OSError:
                pass

# =========================================
# ASR SIDEBAR
# =========================================

def select_asr_sidebar() -> str:
    """
    Render the shared ASR runtime selector
    in the Streamlit sidebar.
    """

    with st.sidebar:
        st.markdown("### 🎙 ASR Backend")

        asr_option_names = list(
            ASR_OPTIONS.keys()
        )

        selected_asr_option = st.selectbox(
            "ASR Model",
            options=asr_option_names,
            index=asr_option_names.index(
                DEFAULT_ASR_OPTION
            ),
            key="selected_asr_option",
            help=(
                "Select the speech recognition "
                "model used for audio input."
            ),
        )

    return selected_asr_option


