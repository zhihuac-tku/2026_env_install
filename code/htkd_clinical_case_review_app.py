 # py code beginning

# py code beginning


## THE CODING PATTERN FOR NRI CODERS BEGINS HERE. ##############################

# =========================================
# 1. STANDARD LIBRARY — REQUIRED BY NRI PATTERN
# =========================================

import sys
import time
import json

from pathlib import Path


# =========================================
# 2. THIRD-PARTY — REQUIRED BY NRI PATTERN
# =========================================

import streamlit as st


# =========================================
# 3. NRI WORKSPACE / PLATFORM DISCOVERY
# =========================================

SCRIPT_PATH = Path(__file__).resolve()

# Current application
CODE_DIR = SCRIPT_PATH.parent
ROOT = CODE_DIR.parent

# Main Python application workspace
PY_ROOT = ROOT.parent

# Shared NRI platform workspace
WORKSPACE_ROOT = PY_ROOT.parent
PLATFORM_ROOT = WORKSPACE_ROOT / "platform"


# Application / domain packages
if str(PY_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PY_ROOT),
    )


# Shared NRI platform packages
if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PLATFORM_ROOT),
    )

# =========================================
# 4. NRI CORE — REQUIRED
# =========================================

from nri_code_core.ui.ui_common import (
    apply_nri_style,
)

from nri_code_core.db.db_runtime import (
    configure_database_runtime,
    get_engine,
    select_database_sidebar,
    verify_database,
)

from nri_ai_core.ai_runtime import (
    configure_llm_runtime,
    select_llm_sidebar,
)

from nri_code_core.asr.asr_runtime import (
    select_asr_sidebar,
)

from nri_code_core.asr.asr_ui import (
    render_asr_input,
)


# =========================================
# 4A. HTKD AGENT
# =========================================

from agents.htkd_clinical_case_preparation_agent import (
    create_htkd_clinical_case_preparation_agent,
)

from agents.htkd_clinical_case_review_agent import (
    HTKDClinicalReviewDeps,
    create_htkd_clinical_case_review_agent,
)

from models.htkd_clinical_case_review_models import (
    PreparedClinicalCase,
)

from htkd.ui.clinical_review_ui import (
    render_clinical_case_review,
)

# =========================================
# 5. APPLICATION CONFIGURATION
# =========================================

APP_NAME = "Edge Clinical Case Review Assistant"
APP_ICON = "🩺"

DB_NAME = "htkd_db"
DEFAULT_DB_ENV = "MacBook"

NRI_INTRANET_DB_HOST = "192.168.184.13"
NRI_INTRANET_DB_PORT = 5432


# =========================================
# 6. STREAMLIT PAGE
# =========================================

st.set_page_config(
    page_title=APP_NAME,
    page_icon=APP_ICON,
    layout="wide",
)


# =========================================

# 7. NRI CORE INITIALIZATION

# =========================================

apply_nri_style()

with st.sidebar:
    st.markdown("### NRI Healthcare")
    st.caption(
        "Edge Clinical Case Review Assistant"
    )


## THE END OF THE NRI CODING PATTERN ###########################################


# =========================================
# 8. DATABASE RUNTIME INITIALIZATION
# =========================================

configure_database_runtime(
    db_name=DB_NAME,
    default_env=DEFAULT_DB_ENV,
    intranet_host=NRI_INTRANET_DB_HOST,
    intranet_port=NRI_INTRANET_DB_PORT,
)

db_env, dsn, db_session_box = (
    select_database_sidebar()
)

engine = get_engine(
    dsn
)

verify_database(
    engine
)

# -----------------------------------------
# LLM Configuration
# -----------------------------------------

ENABLE_LLM = True

DEFAULT_LLM_ENV = "Local Notebook"
DEFAULT_MODEL = "gemma4:latest"

NRI_INTRANET_LLM_HOST = "192.168.184.13"
NRI_INTRANET_LLM_PORT = 11434

# =========================================
# 9. CLINICAL AI PROMPTS
# =========================================

def build_clinical_ai_system_prompt() -> str:
    """
    Build the system instructions for
    clinical case data preparation.
    """

    return """
你是 HTKD Clinical Case Data Preparation Assistant。

你的工作不是診斷疾病，
也不是提供臨床處置建議。

你的工作是將醫師輸入或 ASR 轉錄後，
並經醫師確認的臨床案例內容，
整理成可供後續 HTKD mapping、
HIS data linking 與 SOP evidence retrieval
使用的臨床案例資訊。

重要規則：

1. 只能使用原始案例中明確提供的資訊。

2. 不得自行增加或推測：
   - 診斷
   - 病史
   - 症狀
   - 檢驗結果
   - 生命徵象
   - 用藥
   - 過敏
   - 臨床處置

3. 必須保留具有臨床意義的資訊，
   包括：
   - 年齡
   - 性別
   - 症狀
   - 臨床發現
   - 陰性發現
   - 發病時間
   - 病程
   - 既往病史
   - 用藥
   - 過敏
   - 已提供的檢驗或生命徵象

4. 必須移除或遮罩可直接識別病人的個人資料，
   例如：
   - 姓名
   - 身分證字號
   - 電話
   - Email
   - 地址
   - 病歷號
   - 其他直接識別資訊

5. 個人資料移除後，
   不得改變原本的臨床意義。

6. 未提供的資訊標示為「未提供」。

7. 不確定或無法確認的資訊，
   標示為「無法確認」。

8. 不進行 ICD、SNOMED CT、LOINC
   或其他 terminology mapping。

9. 不查詢或假設任何 HIS 資料。

10. 不提供診斷、鑑別診斷、
    治療建議或臨床處置建議。

11. 使用繁體中文。

你的輸出是「準備好的臨床案例資料」，
供後續系統進行 HTKD mapping、
HIS linking 與 SOP evidence retrieval。
""".strip()


def build_clinical_case_prompt(
    case_text: str,
) -> str:
    """
    Build the task prompt for clinical
    case data preparation.
    """

    case_text = str(
        case_text
        or ""
    ).strip()

    if not case_text:
        raise ValueError(
            "Clinical case text is empty."
        )

    return f"""
    請整理以下由醫師確認後的臨床案例。

    ==============================
    ORIGINAL CLINICAL CASE
    ==============================

    {case_text}

    ==============================

    請將原始案例整理成指定的
    PreparedClinicalCase 結構。

    重要規則：

    1. 只使用原始案例明確提供的資訊。

    2. 不得自行推測診斷或增加不存在的資訊。

    3. current_findings 只放案例中明確存在的
      症狀或臨床發現。

    4. negative_findings 只放案例中明確否認
      或表示不存在的症狀。

    5. medical_history 只放明確提供的既往病史。

    6. medications 只放案例中實際提到的用藥資訊。
      如果不知道確切藥名，不要自行推測。

    7. age 與 sex 只在案例明確提供時填入。

    8. 保留 onset、時間與重要描述。

    9. 直接識別病人的資訊不得放入任何臨床欄位。

    10. 若發現姓名、身分證、電話、Email、
        地址、病歷號或其他直接識別資訊：
        - pii.detected = true
        - 在 pii.removed_types 記錄資料類型
        - 不得在輸出中重現原始個人資料

    11. 不進行：
        - 診斷
        - 鑑別診斷
        - ICD mapping
        - SNOMED CT mapping
        - LOINC mapping
        - HIS 查詢
        - SOP recommendation
        - clinical action recommendation
    """.strip()


def prepare_clinical_case(
    *,
    case_text: str,
    llm_cfg: dict,
) -> PreparedClinicalCase:
    """
    Run the HTKD Clinical Case Review Agent
    against the confirmed clinical case.
    """

    case_text = str(
        case_text
        or ""
    ).strip()

    if not case_text:
        raise ValueError(
            "Clinical case text is empty."
        )

    if not llm_cfg:
        raise RuntimeError(
            "LLM configuration is not available."
        )

    if not llm_cfg.get(
        "enabled",
        True,
    ):
        raise RuntimeError(
            "LLM is not enabled."
        )

    # -------------------------------------
    # Build prompts
    # -------------------------------------

    system_prompt = (
        build_clinical_ai_system_prompt()
    )

    task_prompt = (
        build_clinical_case_prompt(
            case_text
        )
    )

    # -------------------------------------
    # Create HTKD Clinical Agent
    # -------------------------------------

    agent = create_htkd_clinical_case_preparation_agent(
        llm_cfg
    )

    # -------------------------------------
    # Run AI analysis
    # -------------------------------------

    result = agent.run_sync(
        task_prompt,
        instructions=system_prompt,
    )

    prepared_case = result.output

    if not isinstance(
        prepared_case,
        PreparedClinicalCase,
    ):
        raise RuntimeError(
            "Clinical case preparation returned "
            "an invalid result."
        )

    return prepared_case
# ==========================================================
# 10. APPLICATION RUNTIME INITIALIZATION
# ==========================================================

# -----------------------------------------
# AI Runtime
# -----------------------------------------

configure_llm_runtime(
    default_model=DEFAULT_MODEL,
    default_env=DEFAULT_LLM_ENV,
    intranet_host=NRI_INTRANET_LLM_HOST,
    intranet_port=NRI_INTRANET_LLM_PORT,
)

if ENABLE_LLM:
    llm_cfg = select_llm_sidebar()
else:
    llm_cfg = {
        "enabled": False,
        "model": "",
    }


# -----------------------------------------
# ASR Runtime
# -----------------------------------------

selected_asr_option = (
    select_asr_sidebar()
)


# ==========================================================
# 11. APPLICATION UI
# ==========================================================

# =========================================
# KIOSK NAVIGATION STATE
# =========================================

if "kiosk_step" not in st.session_state:
    st.session_state[
        "kiosk_step"
    ] = 1

if "kiosk_max_step" not in st.session_state:
    st.session_state[
        "kiosk_max_step"
    ] = 1


def go_to_kiosk_step(
    step: int,
):
    step = max(
        1,
        min(
            5,
            int(step),
        ),
    )

    st.session_state[
        "kiosk_step"
    ] = step

    st.session_state[
        "kiosk_max_step"
    ] = max(
        st.session_state.get(
            "kiosk_max_step",
            1,
        ),
        step,
    )

    st.rerun()


current_step = st.session_state[
    "kiosk_step"
]


# =========================================
# KIOSK STEP INDICATOR
# =========================================

step_labels = [
    "開始",
    "案例輸入",
    "確認",
    "處理",
    "結果",
]

step_cols = st.columns(
    len(step_labels)
)

for index, label in enumerate(
    step_labels,
    start=1,
):

    with step_cols[
        index - 1
    ]:

        if index < current_step:
            icon = "🟢"

        elif index == current_step:
            icon = "🟩"

        else:
            icon = "⚪"

        st.markdown(
            f"<div style='text-align:center;'>"
            f"<div style='font-size:22px;'>{icon}</div>"
            f"<div style='font-size:12px;'>{label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("---")


# =========================================
# PAGE 1 — WELCOME
# =========================================

if current_step == 1:

    st.markdown(
        """
<div style="text-align:center; padding-top:40px; padding-bottom:20px;">

<div style="
font-size:30px;
font-weight:800;
margin-bottom:22px;
">
🩺 Edge Clinical Case Review Assistant
</div>

<div style="
max-width:720px;
margin:0 auto 24px auto;
padding:26px;
border-radius:22px;
font-size:24px;
font-weight:700;
">
醫師可使用文字或語音輸入目前臨床案例。
</div>

<div style="
font-size:18px;
line-height:1.8;
margin-bottom:20px;
">
第一版先建立可靠的案例輸入與確認流程。<br>
後續再由應用需求加入 Clinical Agent、HTKD tools 與醫院 HIS tools。
</div>

</div>
""",
        unsafe_allow_html=True,
    )

    st.write("")

    _, button_col, _ = (
        st.columns(
            [1, 2, 1]
        )
    )

    with button_col:

        if st.button(
            "🚀 開始案例輸入",
            type="primary",
            use_container_width=True,
            key="kiosk_start",
        ):
            go_to_kiosk_step(
                2
            )


# =========================================
# KIOSK AUDIO INPUT — LARGE TOUCH TARGET
# =========================================

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
# PAGE 2 — CLINICAL CASE INPUT
# =========================================

if current_step == 2:

    st.subheader(
        "🎙️ 臨床案例輸入"
    )

    st.caption(
        "可輸入目前症狀、病史、用藥或其他希望 AI 協助整理的案例資訊。"
    )

    text_tab, voice_tab = st.tabs([
        "⌨️ 文字輸入",
        "🎙️ 語音輸入",
    ])

    # -------------------------------------
    # TEXT INPUT
    # -------------------------------------
    with text_tab:

        typed_case = st.text_area(
            "請輸入臨床案例",
            value=st.session_state.get(
                "clinical_case_text",
                "",
            ),
            height=180,
            key="clinical_case_text",
            placeholder=(
                "例如：65 歲男性，有糖尿病病史，"
                "昨天晚上開始發燒，今天有頭痛與肌肉痠痛……"
            ),
        )

    # -------------------------------------
    # VOICE INPUT
    # -------------------------------------
    with voice_tab:

        transcript_editor = render_asr_input(
            asr_option=selected_asr_option,
            key_prefix="clinical_case",
            title=(
                "🎙️ 按下麥克風，"
                "口述目前臨床案例"
            ),
            instruction=(
                "可描述目前症狀、相關病史、"
                "用藥與其他重要資訊。"
                "說完後停止錄音，"
                "再確認或修改辨識文字。"
            ),
            recorder_label=(
                "錄製臨床案例"
            ),
            transcript_label=(
                "請確認或修改語音辨識內容"
            ),
            language="zh",
        )

    # -------------------------------------
    # SELECT CONTENT TO USE
    # -------------------------------------
    st.divider()

    input_source = st.radio(
        "請選擇本次案例內容",
        [
            "文字輸入",
            "語音辨識內容",
        ],
        horizontal=True,
        key="clinical_case_input_source",
        help=(
            "如果同時有文字與語音內容，"
            "請選擇本次要送入案例流程的內容。"
        ),
    )

    # -------------------------------------
    # BUILD FINAL CASE TEXT
    # -------------------------------------
    if input_source == "文字輸入":

        final_case_text = (
            typed_case.strip()
        )

        source_type = "text"

    else:

        final_case_text = (
            transcript_editor.strip()
        )

        source_type = "voice"

    # -------------------------------------
    # FINAL CASE PREVIEW
    # -------------------------------------
    if final_case_text:

        st.caption(
            "本次確認的案例內容："
        )

        st.info(
            final_case_text
        )

    # -------------------------------------
    # CONFIRM CASE INPUT
    # -------------------------------------
    if st.button(
        "✅ 確認案例內容",
        type="primary",
        use_container_width=True,
        key="save_clinical_case",
    ):

        if not final_case_text:

            if source_type == "voice":

                st.warning(
                    "目前沒有語音辨識內容，"
                    "請先完成錄音與語音辨識。"
                )

            else:

                st.warning(
                    "請先輸入臨床案例。"
                )

        else:

            # =================================
            # Clear Future Downstream Results
            # =================================
            downstream_keys = [
                "clinical_case_analysis",
                "clinical_case_analysis_pack",
                "clinical_case_review",
                "clinical_case_review_pack",
            ]

            for key in downstream_keys:

                st.session_state.pop(
                    key,
                    None,
                )

            # =================================
            # Save Confirmed Clinical Case
            # =================================
            st.session_state[
                "clinical_case_input_pack"
            ] = {
                "case_text":
                    final_case_text,

                "input_source":
                    source_type,

                "asr_model": (
                    selected_asr_option
                    if source_type == "voice"
                    else None
                ),

                "created_at":
                    time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
            }

            go_to_kiosk_step(
                3
            )


# =========================================
# PAGE 3 — CONFIRMED CASE
# =========================================

if current_step == 3:

    st.subheader(
        "📋 已確認的臨床案例"
    )

    clinical_case_input_pack = (
        st.session_state.get(
            "clinical_case_input_pack"
        )
    )

    if not clinical_case_input_pack:

        st.warning(
            "尚未建立臨床案例內容。"
        )

        if st.button(
            "← 返回案例輸入",
            use_container_width=True,
            key="return_to_case_input_empty",
        ):
            go_to_kiosk_step(
                2
            )

    else:

        case_text = str(
            clinical_case_input_pack.get(
                "case_text",
                "",
            )
            or ""
        ).strip()

        input_source = (
            clinical_case_input_pack.get(
                "input_source"
            )
        )

        asr_model = (
            clinical_case_input_pack.get(
                "asr_model"
            )
        )

        created_at = (
            clinical_case_input_pack.get(
                "created_at"
            )
        )

        # ---------------------------------
        # Confirmed Case Text
        # ---------------------------------

        st.markdown(
            "### Case Text"
        )

        st.info(
            case_text
        )

        # ---------------------------------
        # Case Metadata
        # ---------------------------------

        col1, col2, col3 = st.columns(
            3
        )

        with col1:

            st.caption(
                "Input Source"
            )

            st.write(
                "Voice"
                if input_source == "voice"
                else "Text"
            )

        with col2:

            st.caption(
                "ASR Model"
            )

            st.write(
                asr_model
                if asr_model
                else "—"
            )

        with col3:

            st.caption(
                "Created At"
            )

            st.write(
                created_at
                if created_at
                else "—"
            )

        st.divider()

        st.caption(
            "確認案例內容後，下一步將進入臨床案例處理流程。"
            "Clinical Agent、HTKD 與後續臨床證據查詢"
            "將從下一階段開始執行。"
        )

        # ---------------------------------
        # Navigation
        # ---------------------------------

        left_col, right_col = st.columns(
            2
        )

        with left_col:

            if st.button(
                "← 修改案例內容",
                use_container_width=True,
                key="edit_clinical_case",
            ):

                go_to_kiosk_step(
                    2
                )

        with right_col:

            if st.button(
                "確認案例並開始處理 →",
                type="primary",
                use_container_width=True,
                key="start_clinical_case_review",
            ):

                if not case_text:

                    st.warning(
                        "沒有可供處理的臨床案例內容。"
                    )

                    st.stop()

                # ---------------------------------
                # Clear Previous Results
                # ---------------------------------

                st.session_state.pop(
                    "clinical_case_preparation_pack",
                    None,
                )

                st.session_state.pop(
                    "clinical_case_review_pack",
                    None,
                )

                # ---------------------------------
                # PAGE 3 — Prepare Clinical Case
                # ---------------------------------

                try:

                    with st.spinner(
                        "正在準備臨床案例資料..."
                    ):

                        prepared_case = (
                            prepare_clinical_case(
                                case_text=case_text,
                                llm_cfg=llm_cfg,
                            )
                        )

                    # ---------------------------------
                    # PAGE 3 JSON
                    # ---------------------------------

                    clinical_case_preparation_pack = {
                        "original_case": {
                            "case_text":
                                case_text,

                            "input_source":
                                input_source,

                            "asr_model":
                                asr_model,

                            "created_at":
                                created_at,
                        },

                        "prepared_case":
                            prepared_case.model_dump(),

                        "prepared_at":
                            time.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                    }

                    st.session_state[
                        "clinical_case_preparation_pack"
                    ] = (
                        clinical_case_preparation_pack
                    )

                    # ---------------------------------
                    # Move to Page 4
                    # ---------------------------------

                    go_to_kiosk_step(
                        4
                    )

                except Exception as exc:

                    st.error(
                        "Clinical case preparation failed."
                    )

                    st.exception(
                        exc
                    )

# =========================================
# PAGE 4 — CLINICAL CASE REVIEW / REACT
# =========================================

if current_step == 4:

    st.subheader(
        "⚙️ Clinical Case Review"
    )

    # -------------------------------------
    # LOAD PAGE 3 JSON
    # -------------------------------------

    preparation_pack = (
        st.session_state.get(
            "clinical_case_preparation_pack"
        )
    )

    if not preparation_pack:

        st.warning(
            "尚未建立 Page 3 臨床案例資料。"
        )

        st.stop()

    prepared_case = (
        preparation_pack.get(
            "prepared_case",
            {}
        )
    )

    if not prepared_case:

        st.warning(
            "Page 3 PreparedClinicalCase 不存在。"
        )

        st.stop()

    # -------------------------------------
    # PROCESSING STATUS
    # -------------------------------------

    st.markdown(
        "### 處理狀態"
    )

    st.write(
        "✓ Page 3 臨床案例資料已載入"
    )

    # -------------------------------------
    # AVOID DUPLICATE AGENT RUN
    # -------------------------------------

    existing_review_pack = (
        st.session_state.get(
            "clinical_case_review_pack"
        )
    )

    if existing_review_pack:

        st.write(
            "✓ Clinical Review 已完成"
        )

        go_to_kiosk_step(
            5
        )

        st.stop()

    # -------------------------------------
    # PAGE 4 — REACT AGENT
    # -------------------------------------

    try:

        with st.spinner(
            "Clinical Review Agent 正在進行 "
            "HTKD 臨床證據查詢..."
        ):

            # ---------------------------------
            # CREATE AGENT
            # ---------------------------------

            agent = (
                create_htkd_clinical_case_review_agent(
                    llm_cfg
                )
            )

            # ---------------------------------
            # AGENT DEPENDENCIES
            # ---------------------------------

            agent_deps = (
                HTKDClinicalReviewDeps(
                    engine=engine,
                )
            )

            # ---------------------------------
            # PREPARED CASE INPUT
            # ---------------------------------

            case_prompt = json.dumps(
                prepared_case,
                ensure_ascii=False,
                indent=2,
            )

            # ---------------------------------
            # RUN REACT
            #
            # Agent decides:
            #
            # Reason
            #   ↓
            # Action / Tool
            #   ↓
            # Observation
            #   ↓
            # Reason again
            #   ↓
            # Final structured output
            #
            # Page 4 does NOT decide
            # which WHO tool to call.
            # ---------------------------------

            result = agent.run_sync(
                case_prompt,
                deps=agent_deps,
            )

            clinical_review_result = (
                result.output
            )

        # -------------------------------------
        # AGENT COMPLETED
        # -------------------------------------

        st.write(
            "✓ Clinical Review Agent 已完成"
        )

        # -------------------------------------
        # GET ACTUAL TOOL OBSERVATIONS
        #
        # Same pattern as LilyLab:
        #
        # weather_context
        # product_results
        #
        # Here:
        # who_evidence
        # -------------------------------------

        who_evidence = (
            agent_deps.who_evidence
            or []
        )

        # -------------------------------------
        # REACT STATUS
        # -------------------------------------

        if agent_deps.who_tool_called:

            st.write(
                "✓ WHO ICD Tool 已呼叫"
            )

            st.write(
                "✓ WHO ICD Tool Calls："
                f"{agent_deps.who_tool_call_count}"
            )

            st.write(
                "✓ WHO ICD Observations："
                f"{agent_deps.who_observation_count}"
            )

        else:

            st.warning(
                "本次 Clinical Review Agent "
                "沒有呼叫 WHO ICD Tool。"
            )

        # -------------------------------------
        # SAVE AGENT TRACE
        #
        # Same idea as LilyLab:
        #
        # weather_tool_called
        # product_search_called
        #
        # Here:
        # who_tool_called
        # -------------------------------------

        agent_trace = {

            "who_tool_called":
                agent_deps.who_tool_called,

            "who_tool_call_count":
                agent_deps.who_tool_call_count,

            "who_observation_count":
                agent_deps.who_observation_count,
        }

        st.session_state[
            "clinical_review_agent_trace"
        ] = agent_trace

        # -------------------------------------
        # PAGE 4 JSON
        # -------------------------------------

        clinical_case_review_pack = {

            # ---------------------------------
            # ACTUAL HTKD OBSERVATIONS
            #
            # These come from real ReAct
            # tool execution.
            # ---------------------------------

            "who_evidence":
                who_evidence,

            # ---------------------------------
            # FUTURE REACT CAPABILITIES
            # ---------------------------------

            "tw_icd": [],

            "medication": [],

            "his": [],

            "sop": [],

            # ---------------------------------
            # AGENT FINAL STRUCTURED OUTPUT
            # ---------------------------------

            "review":
                clinical_review_result.model_dump(),

            # ---------------------------------
            # REACT TRACE
            # ---------------------------------

            "agent_trace":
                agent_trace,

            # ---------------------------------
            # REVIEW TIME
            # ---------------------------------

            "reviewed_at":
                time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
        }

        # -------------------------------------
        # SAVE PAGE 4 JSON
        # -------------------------------------

        st.session_state[
            "clinical_case_review_pack"
        ] = (
            clinical_case_review_pack
        )

        # -------------------------------------
        # MOVE TO PAGE 5
        # -------------------------------------

        go_to_kiosk_step(
            5
        )

    except Exception as exc:

        st.error(
            "Clinical Review Agent / ReAct "
            "處理失敗。"
        )

        st.exception(
            exc
        )

        st.stop()

# =========================================
# PAGE 5 — CLINICAL CASE REVIEW OUTPUT
# =========================================

if current_step == 5:

    st.subheader(
        "📋 Clinical Case Review"
    )

    # -------------------------------------
    # Load Page 3 JSON
    # -------------------------------------

    preparation_pack = (
        st.session_state.get(
            "clinical_case_preparation_pack",
            {},
        )
    )

    # -------------------------------------
    # Load Page 4 JSON
    # -------------------------------------

    review_pack = (
        st.session_state.get(
            "clinical_case_review_pack",
            {},
        )
    )

    # -------------------------------------
    # Validate Page 3 Result
    # -------------------------------------

    if not preparation_pack:

        st.warning(
            "尚未建立臨床案例資料。"
        )

        if st.button(
            "← 返回案例確認",
            use_container_width=True,
            key="return_to_case_confirm_empty",
        ):

            go_to_kiosk_step(
                3
            )

        st.stop()

    # =====================================
    # CLINICAL REVIEW UI
    # =====================================

    render_clinical_case_review(
        preparation_pack=preparation_pack,
        review_pack=review_pack,
    )

    # =====================================
    # NAVIGATION
    # =====================================

    st.divider()

    if st.button(
        "← 返回案例確認",
        use_container_width=True,
        key="return_to_confirmed_case",
    ):

        go_to_kiosk_step(
            3
        )

