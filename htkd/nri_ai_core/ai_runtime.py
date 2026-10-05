 # py code beginning


from __future__ import annotations
import json
import httpx
import streamlit as st
from nri_code_core.utils.core_utils import session_default

DEFAULT_LLM_ENV="Local Notebook"
DEFAULT_MODEL="gemma4:latest"
NRI_INTRANET_HOST="192.168.10.10"
NRI_INTRANET_LLM_PORT=11434
LLM_ENVIRONMENTS={}

# NCHC RAP can require substantially more time for multi-step Agent requests
# than for ordinary one-shot chat/report generation.
NCHC_RAP_AGENT_TIMEOUT_SECONDS = 600.0
AZURE_OPENAI_AGENT_TIMEOUT_SECONDS = 600.0

def configure_llm_runtime(default_model=DEFAULT_MODEL, default_env=DEFAULT_LLM_ENV, intranet_host=NRI_INTRANET_HOST, intranet_port=NRI_INTRANET_LLM_PORT):
    global DEFAULT_MODEL, DEFAULT_LLM_ENV, NRI_INTRANET_HOST, NRI_INTRANET_LLM_PORT, LLM_ENVIRONMENTS
    DEFAULT_MODEL=default_model; DEFAULT_LLM_ENV=default_env; NRI_INTRANET_HOST=intranet_host; NRI_INTRANET_LLM_PORT=intranet_port
    LLM_ENVIRONMENTS=build_llm_envs(DEFAULT_MODEL)
    return LLM_ENVIRONMENTS

def build_llm_envs(default_model: str) -> dict:
    return {
        "Local Notebook": {
            "label": "Local Ollama on this machine",
            "base_url": "http://127.0.0.1:11434",
            "default_model": default_model,
        },
        "Center MacBook Pro": {
            "label": "Center inference server / MacBook Pro 128GB",
            "base_url": "http://<center-macbook-ip>:11434",
            "default_model": default_model,
        },
        "NRI Intranet LLM": {
            "label": "NRI intranet inference endpoint",
            "base_url": f"http://{NRI_INTRANET_HOST}:{NRI_INTRANET_LLM_PORT}",
            "default_model": default_model,
        },
        "NCHC RAP API": {
            "label": "NCHC RAP / GenAI API",
            "base_url": "https://portal.genai.nchc.org.tw/api/v1",
            "default_model": "",
            "api_type": "nchc_rap",
        },
        "Azure OpenAI API": {
            "label": "Azure OpenAI v1 API",
            "base_url": "https://dxtest1.openai.azure.com/openai/v1/",
            "default_model": "gpt-5.6-luna",
            "api_type": "azure_openai",
        },
        "Disabled": {
            "label": "No LLM backend",
            "base_url": "",
            "default_model": "",
        },
    }

def ollama_list_models(base_url: str):
    url = base_url.rstrip("/") + "/api/tags"

    with httpx.Client(timeout=20) as client:
        resp = client.get(url)

    resp.raise_for_status()

    data = resp.json()

    return [
        m["name"]
        for m in data.get("models", [])
    ]

def nchc_rap_chat(base_url, api_key, model, messages, temperature=0.2, max_tokens=3000):
    url = base_url.rstrip("/") + "/chat/completions"

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(url, headers=headers, json=payload)

    resp.raise_for_status()
    data = resp.json()

    return data["choices"][0]["message"]["content"]

def azure_openai_chat(
    base_url,
    api_key,
    model,
    messages,
    temperature=0.2,
    max_tokens=3000,
):
    from openai import OpenAI

    client = OpenAI(
        base_url=str(base_url or "").rstrip("/") + "/",
        api_key=api_key,
        timeout=httpx.Timeout(
            AZURE_OPENAI_AGENT_TIMEOUT_SECONDS,
            connect=15.0,
        ),
        max_retries=1,
    )

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content or ""

def is_asr_model(model_name: str) -> bool:
    """
    Return True when a model name clearly represents an ASR /
    speech-to-text model.

    The normal LLM selector should not expose ASR models. ASR model
    selection belongs to the separate shared ASR runtime.
    """
    normalized = str(model_name or "").strip().lower()

    if not normalized:
        return False

    asr_markers = (
        "whisper",
        "speech-to-text",
        "speech_to_text",
        "speech2text",
    )

    if any(
        marker in normalized
        for marker in asr_markers
    ):
        return True

    # Match ASR when it appears as a model-name token, while avoiding
    # accidental substring matches inside unrelated model names.
    normalized_tokens = (
        normalized
        .replace("_", "-")
        .replace("/", "-")
        .replace(":", "-")
        .split("-")
    )

    return "asr" in normalized_tokens


def nchc_rap_list_models(base_url: str, api_key: str):
    url = base_url.rstrip("/") + "/models"

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=headers)

    resp.raise_for_status()
    data = resp.json()

    model_ids = [
        m.get("id")
        for m in data.get("data", [])
        if m.get("id")
    ]

    return [
        model_id
        for model_id in model_ids
        if not is_asr_model(model_id)
    ]

def get_nchc_rap_api_key():
    session_default("nchc_rap_api_key", "")

    api_key = st.text_input(
        "NCHC RAP API Key",
        value=st.session_state["nchc_rap_api_key"],
        type="password",
        help="Enter once per Streamlit session.",
    )

    st.session_state["nchc_rap_api_key"] = api_key

    return api_key

def get_azure_openai_api_key():
    session_default("azure_openai_api_key", "")

    api_key = st.text_input(
        "Azure OpenAI API Key",
        value=st.session_state["azure_openai_api_key"],
        type="password",
        help="Enter once per Streamlit session.",
    )

    st.session_state["azure_openai_api_key"] = api_key

    return api_key

def select_llm_sidebar():
    st.sidebar.subheader("🧠 LLM Backend")

    llm_options = list(LLM_ENVIRONMENTS.keys())

    session_default("llm_environment", DEFAULT_LLM_ENV)

    llm_env = st.sidebar.selectbox(
        "LLM Environment",
        llm_options,
        key="llm_environment",
    )

    llm_cfg = LLM_ENVIRONMENTS[llm_env]
    api_type = llm_cfg.get("api_type", "ollama")

    if llm_env == "Disabled":
        st.sidebar.caption(llm_cfg["label"])
        return {
            "enabled": False,
            "env": llm_env,
            "api_type": api_type,
            "base_url": "",
            "api_key": "",
            "model": "",
            "temperature": 0.2,
            "num_predict": 5000,
            "num_ctx": 0,
        }

    with st.sidebar.expander("LLM connection detail", expanded=False):
        st.caption(llm_cfg["label"])

        base_url_key = f"llm_base_url_{llm_env}"

        if base_url_key not in st.session_state:
            st.session_state[base_url_key] = llm_cfg["base_url"]

        base_url = st.text_input(
            "LLM API URL",
            key=base_url_key,
        )

        api_key = ""

        if api_type == "nchc_rap":
            api_key = get_nchc_rap_api_key()

        elif api_type == "azure_openai":
            api_key = get_azure_openai_api_key()

        model_cache_key = f"llm_models_{llm_env}"
        models = []

        if st.button("🔄 Refresh LLM models", use_container_width=True):
            try:
                if api_type == "nchc_rap":
                    if not api_key:
                        st.warning("Please enter NCHC RAP API key first.")
                        models = []
                    else:
                        models = nchc_rap_list_models(base_url, api_key)

                elif api_type == "azure_openai":
                    models = []
                    st.info(
                        "Enter the Azure OpenAI deployment name below."
                    )

                else:
                    models = ollama_list_models(base_url)

                st.session_state[model_cache_key] = models

                if api_type != "azure_openai":
                    st.success(f"Found {len(models)} models")

            except Exception as e:
                st.error(f"LLM model refresh failed: {e}")

        if not models:
            models = st.session_state.get(model_cache_key, [])

        if models:
            default_model = llm_cfg["default_model"]

            default_index = (
                models.index(default_model)
                if default_model in models
                else 0
            )

            model = st.selectbox(
                "LLM model",
                models,
                index=default_index,
            )
        else:
            model_label = (
                "Azure deployment name"
                if api_type == "azure_openai"
                else "LLM model"
            )

            model = st.text_input(
                model_label,
                value=llm_cfg["default_model"],
            )

        session_default("llm_temperature", 0.2)

        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            step=0.1,
            key="llm_temperature",
        )

        session_default("llm_num_predict", 5000)

        num_predict = st.slider(
            "LLM Max Output Tokens",
            min_value=300,
            max_value=50000,
            step=100,
            key="llm_num_predict",
        )

        auto_num_ctx = max(
            4096,
            int(num_predict * 2),
        )
        st.sidebar.caption(
            f"Auto Context Window: {auto_num_ctx:,} tokens"
        )

        return {
            "enabled": True,
            "env": llm_env,
            "api_type": api_type,
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": auto_num_ctx,
        }

def build_llm_generation_metadata(llm_cfg):

    if not llm_cfg:
        return {
            "generated_by": "LLM disabled",
            "model": "",
            "llm_environment": "",
            "temperature": "",
            "num_predict": "",
        }

    api_type = llm_cfg.get("api_type", "ollama")

    if api_type == "nchc_rap":
        generated_by = "NCHC RAP / GenAI API"

    elif api_type == "azure_openai":
        generated_by = "Azure OpenAI API"

    else:
        generated_by = "Edge AI / Local Ollama"

    return {
        "generated_by": generated_by,
        "model": llm_cfg.get("model"),
        "llm_environment": llm_cfg.get("env"),
        "temperature": llm_cfg.get("temperature"),
        "num_predict": llm_cfg.get("num_predict"),
    }

def run_ai_copilot_stream(
    llm_cfg,
    messages,
    session_key,
    button_label="🚀 Generate AI Report",
    spinner_text="Generating AI report...",
):
    if st.button(button_label, use_container_width=True):

        if not llm_cfg or not llm_cfg.get("enabled"):
            st.warning("LLM backend is disabled.")
            st.stop()

        try:
            placeholder = st.empty()

            with st.spinner(spinner_text):

                if llm_cfg.get("api_type") == "nchc_rap":

                    report_text = nchc_rap_chat(
                        base_url=llm_cfg["base_url"],
                        api_key=llm_cfg["api_key"],
                        model=llm_cfg["model"],
                        messages=messages,
                        temperature=llm_cfg["temperature"],
                        max_tokens=llm_cfg["num_predict"],
                    )

                    placeholder.markdown(report_text)

                elif llm_cfg.get("api_type") == "azure_openai":

                    report_text = azure_openai_chat(
                        base_url=llm_cfg["base_url"],
                        api_key=llm_cfg["api_key"],
                        model=llm_cfg["model"],
                        messages=messages,
                        temperature=llm_cfg["temperature"],
                        max_tokens=llm_cfg["num_predict"],
                    )

                    placeholder.markdown(report_text)

                else:
                    parts = []

                    for delta in ollama_chat_stream(
                        base_url=llm_cfg["base_url"],
                        model=llm_cfg["model"],
                        messages=messages,
                        temperature=llm_cfg["temperature"],
                        num_predict=llm_cfg["num_predict"],
                        num_ctx=llm_cfg["num_ctx"],
                    ):
                        parts.append(delta)
                        placeholder.markdown("".join(parts))

                    report_text = "".join(parts)

            st.session_state[session_key] = report_text
            st.success("✅ AI report generated.")

        except Exception as e:
            st.error(str(e))


# ============================================================
# PYDANTIC AI MODEL FACTORY
# ============================================================

def _ollama_openai_base_url(
    base_url: str,
) -> str:
    """
    Convert an Ollama server URL to its OpenAI-compatible
    endpoint used by Pydantic AI.
    """

    clean = str(
        base_url or ""
    ).rstrip("/")

    if clean.endswith("/v1"):
        return clean

    return clean + "/v1"


def build_agent_model(
    llm_cfg: dict,
):
    """
    Build a Pydantic AI model from the standard NRI LLM
    configuration.

    Supported providers:
    - Ollama: local / intranet
    - NCHC RAP: OpenAI-compatible API
    - Azure OpenAI: OpenAI v1-compatible API
    """

    if (
        not llm_cfg
        or not llm_cfg.get(
            "enabled"
        )
    ):
        raise RuntimeError(
            "LLM backend is disabled."
        )

    model_name = str(
        llm_cfg.get(
            "model",
            "",
        )
        or ""
    ).strip()

    if not model_name:
        raise RuntimeError(
            "No LLM model is selected."
        )

    api_type = llm_cfg.get(
        "api_type",
        "ollama",
    )

    if api_type == "nchc_rap":
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import (
            OpenAIChatModel,
        )
        from pydantic_ai.providers.openai import (
            OpenAIProvider,
        )

        api_key = str(
            llm_cfg.get(
                "api_key",
                "",
            )
            or ""
        ).strip()

        if not api_key:
            raise RuntimeError(
                "NCHC RAP API key is required."
            )

        client = AsyncOpenAI(
            base_url=str(
                llm_cfg.get(
                    "base_url",
                    "",
                )
            ).rstrip("/"),
            api_key=api_key,
            default_headers={
                "x-api-key": api_key,
            },
            timeout=httpx.Timeout(
                NCHC_RAP_AGENT_TIMEOUT_SECONDS,
                connect=15.0,
            ),
            max_retries=1,
        )

        return OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                openai_client=client,
            ),
        )

    if api_type == "azure_openai":
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import (
            OpenAIChatModel,
        )
        from pydantic_ai.providers.openai import (
            OpenAIProvider,
        )

        api_key = str(
            llm_cfg.get(
                "api_key",
                "",
            )
            or ""
        ).strip()

        if not api_key:
            raise RuntimeError(
                "Azure OpenAI API key is required."
            )

        base_url = str(
            llm_cfg.get(
                "base_url",
                "",
            )
            or ""
        ).rstrip("/") + "/"

        client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=httpx.Timeout(
                AZURE_OPENAI_AGENT_TIMEOUT_SECONDS,
                connect=15.0,
            ),
            max_retries=1,
        )

        return OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                openai_client=client,
            ),
        )

    from pydantic_ai.models.ollama import (
        OllamaModel,
    )
    from pydantic_ai.providers.ollama import (
        OllamaProvider,
    )

    return OllamaModel(
        model_name,
        provider=OllamaProvider(
            base_url=_ollama_openai_base_url(
                llm_cfg.get(
                    "base_url",
                    "",
                )
            ),
        ),
    )



