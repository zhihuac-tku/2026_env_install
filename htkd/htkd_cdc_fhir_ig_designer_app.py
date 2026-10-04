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


# =========================================
# 4A. HTKD CDC FHIR IG
# =========================================

from agents.htkd_cdc_report_requirement_agent import (
    extract_cdc_report_requirements,
)

from agents.htkd_cdc_fhir_mapping_agent import (
    map_cdc_report_to_fhir,
)

from htkd.fhir_ig.document.report_reader import (
    ExtractedReportDocument,
    read_cdc_report,
)

from models.htkd_cdc_fhir_ig_models import (
    CDCFHIRMappingResult,
    CDCReportRequirement,
)

# =========================================
# 5. APPLICATION CONFIGURATION
# =========================================

APP_NAME = "HTKD CDC FHIR IG Designer"
APP_ICON = "🧬"

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
        "HTKD CDC FHIR IG Designer"
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
            7,
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
    "報告上傳",
    "需求確認",
    "IG 比對",
    "Gap / ReAct",
    "設計確認",
    "FSH",
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
🧬 HTKD CDC FHIR IG Designer
</div>

<div style="
max-width:720px;
margin:0 auto 24px auto;
padding:26px;
border-radius:22px;
font-size:24px;
font-weight:700;
">
從實際 CDC 通報文件開始設計 FHIR Implementation Guide。
</div>

<div style="
font-size:18px;
line-height:1.8;
margin-bottom:20px;
">
上傳 CDC 通報文件後，先解析並確認通報需求。<br>
再進行既有 FHIR IG 比對、Gap Analysis、ReAct 設計分析，
最後產生 FSH。
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
            "🚀 開始通報文件分析",
            type="primary",
            use_container_width=True,
            key="kiosk_start",
        ):
            go_to_kiosk_step(
                2
            )


# =========================================
# PAGE 2 — CDC REPORT UPLOAD / READ
# =========================================

if current_step == 2:

    st.subheader(
        "📄 CDC 通報文件上傳"
    )

    st.caption(
        "請上傳實際使用的 CDC 通報文件。"
        "系統將先讀取文件內容與結構，"
        "下一步再由 AI 整理通報需求。"
    )

    # -------------------------------------
    # REPORT FILE UPLOAD
    # -------------------------------------

    uploaded_report = st.file_uploader(
        "上傳 CDC 通報文件",
        type=[
            "odt",
            "xlsx",
            "csv",
            "xml",
            "pdf",
        ],
        key="cdc_report_file",
        help=(
            "目前支援 ODT、Excel、CSV、"
            "XML 與 PDF 文件。"
        ),
    )

    # -------------------------------------
    # FILE INFORMATION
    # -------------------------------------

    if uploaded_report is not None:

        file_name = (
            uploaded_report.name
        )

        file_type = (
            file_name.rsplit(
                ".",
                1,
            )[-1].lower()
            if "." in file_name
            else ""
        )

        file_bytes = (
            uploaded_report.getvalue()
        )

        file_size = len(
            file_bytes
        )

        st.divider()

        st.markdown(
            "#### 📋 文件資訊"
        )

        info_col1, info_col2 = (
            st.columns(2)
        )

        with info_col1:

            st.write(
                f"**檔案名稱：** "
                f"{file_name}"
            )

            st.write(
                f"**檔案格式：** "
                f"{file_type.upper()}"
            )

        with info_col2:

            st.write(
                f"**檔案大小：** "
                f"{file_size / 1024:.1f} KB"
            )

    # -------------------------------------
    # CONFIRM + READ REPORT FILE
    # -------------------------------------

    if st.button(
        "✅ 確認並讀取通報文件",
        type="primary",
        use_container_width=True,
        key="save_cdc_report",
    ):

        if uploaded_report is None:

            st.warning(
                "請先上傳 CDC 通報文件。"
            )

            st.stop()

        file_name = (
            uploaded_report.name
        )

        file_type = (
            file_name.rsplit(
                ".",
                1,
            )[-1].lower()
            if "." in file_name
            else ""
        )

        file_bytes = (
            uploaded_report.getvalue()
        )

        # ---------------------------------
        # Read Document
        # ---------------------------------

        try:

            with st.spinner(
                "正在讀取 CDC 通報文件..."
            ):

                report_document = (
                    read_cdc_report(
                        file_bytes=file_bytes,
                        file_name=file_name,
                        file_type=file_type,
                    )
                )

        except Exception as exc:

            st.error(
                "CDC 通報文件讀取失敗。"
            )

            st.exception(
                exc
            )

            st.stop()

        # ---------------------------------
        # Validate Extracted Content
        # ---------------------------------

        if not (
            report_document.text
            or report_document.paragraphs
            or report_document.tables
            or report_document.sheets
        ):

            st.warning(
                "文件已開啟，但沒有讀取到可分析的內容。"
            )

            if (
                report_document.extraction_notes
            ):

                for note in (
                    report_document.extraction_notes
                ):

                    st.write(
                        f"- {note}"
                    )

            st.stop()

        # ---------------------------------
        # Clear Downstream Results
        # ---------------------------------

        downstream_keys = [
            "cdc_report_requirement_draft",
            "cdc_report_requirement_pack",
            "cdc_fhir_mapping_pack",
            "cdc_fhir_gap_analysis_pack",
            "cdc_fhir_ig_design_pack",
            "cdc_fhir_ig_confirmed_design_pack",
            "cdc_fsh_output",
        ]

        for key in downstream_keys:

            st.session_state.pop(
                key,
                None,
            )

        # ---------------------------------
        # Save Report + Reader Result
        # ---------------------------------

        st.session_state[
            "cdc_report_input_pack"
        ] = {
            "file_name":
                file_name,

            "file_type":
                file_type,

            "file_size":
                len(file_bytes),

            "file_bytes":
                file_bytes,

            "report_document":
                report_document.model_dump(),

            "created_at":
                time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
        }

        go_to_kiosk_step(
            3
        )

# =========================================
# PAGE 3 — REPORT REQUIREMENT CONFIRMATION
# =========================================

if current_step == 3:

    st.subheader(
        "📋 CDC 通報需求確認"
    )

    # =====================================
    # LOAD PAGE 2 RESULT
    # =====================================

    input_pack = (
        st.session_state.get(
            "cdc_report_input_pack"
        )
    )

    if not input_pack:

        st.warning(
            "尚未建立 CDC 通報文件資料。"
        )

        if st.button(
            "← 返回通報文件上傳",
            use_container_width=True,
            key="return_to_report_upload_empty",
        ):
            go_to_kiosk_step(
                2
            )

        st.stop()

    # =====================================
    # RESTORE EXTRACTED DOCUMENT
    # =====================================

    report_document_data = (
        input_pack.get(
            "report_document"
        )
    )

    if not report_document_data:

        st.warning(
            "找不到已解析的 CDC 通報文件內容。"
        )

        st.stop()

    report_document = (
        ExtractedReportDocument.model_validate(
            report_document_data
        )
    )

    # =====================================
    # LOAD REQUIREMENT DRAFT
    # =====================================

    requirement_draft = (
        st.session_state.get(
            "cdc_report_requirement_draft"
        )
    )

    # =====================================
    # ANALYZE REPORT REQUIREMENTS
    # =====================================

    if not requirement_draft:

        st.write(
            f"✓ 已讀取文件："
            f"{input_pack.get('file_name', '')}"
        )

        st.caption(
            "由 AI 整理文件中的通報區段、"
            "欄位、資料型態、選項與複合欄位。"
        )

        if st.button(
            "🔍 分析通報需求",
            type="primary",
            use_container_width=True,
            key="analyze_cdc_requirement",
        ):

            try:

                with st.spinner(
                    "正在整理 CDC 通報需求..."
                ):

                    requirement = (
                        extract_cdc_report_requirements(
                            report_document=(
                                report_document
                            ),
                            llm_cfg=llm_cfg,
                        )
                    )

                # -----------------------------
                # Save Draft JSON
                # -----------------------------

                st.session_state[
                    "cdc_report_requirement_draft"
                ] = (
                    requirement.model_dump(
                        mode="json"
                    )
                )

                st.rerun()

            except Exception as exc:

                st.error(
                    "CDC 通報需求分析失敗。"
                )

                st.exception(
                    exc
                )

                st.stop()

    # =====================================
    # REVIEW REQUIREMENT DRAFT
    # =====================================

    else:

        # ---------------------------------
        # Validate JSON with Pydantic
        # ---------------------------------

        requirement = (
            CDCReportRequirement.model_validate(
                requirement_draft
            )
        )

        st.success(
            "✓ CDC 通報需求分析完成"
        )

        # =================================
        # STRUCTURED JSON
        # =================================

        st.markdown(
            "### Structured Requirement"
        )

        st.caption(
            "此 JSON 為 CDC 通報需求的結構化結果，"
            "確認後將直接提供給 Page 4 "
            "進行 FHIR IG 比對。"
        )

        requirement_json = (
            requirement.model_dump(
                mode="json"
            )
        )

        with st.expander(
            "🧩 CDC Report Requirement JSON",
            expanded=False,
        ):

            st.json(
                requirement_json
            )

        # =================================
        # REPORT INFORMATION
        # =================================

        st.markdown(
            f"### {requirement.report_name}"
        )

        if requirement.report_version:

            st.caption(
                f"版本："
                f"{requirement.report_version}"
            )

        if requirement.report_description:

            st.write(
                requirement.report_description
            )

        # =================================
        # SECTIONS / FIELDS
        # =================================

        for section in (
            requirement.sections
        ):

            with st.expander(
                section.section_name,
                expanded=True,
            ):

                if section.description:

                    st.caption(
                        section.description
                    )

                # -------------------------
                # Fields
                # -------------------------

                for field in (
                    section.fields
                ):

                    st.markdown(
                        f"**{field.field_name}**"
                    )

                    details = []

                    # ---------------------
                    # Data Type
                    # ---------------------

                    if field.data_type:

                        details.append(
                            f"Type: "
                            f"{field.data_type}"
                        )

                    # ---------------------
                    # Required
                    # ---------------------

                    if field.required is True:

                        details.append(
                            "Required: Yes"
                        )

                    elif field.required is False:

                        details.append(
                            "Required: No"
                        )

                    else:

                        details.append(
                            "Required: Unknown"
                        )

                    if details:

                        st.caption(
                            " | ".join(
                                details
                            )
                        )

                    # ---------------------
                    # Simple Field Options
                    # ---------------------

                    if field.options:

                        st.write(
                            "選項："
                            + " / ".join(
                                field.options
                            )
                        )

                    # ---------------------
                    # Composite Components
                    # ---------------------

                    if field.components:

                        st.caption(
                            "Composite Components"
                        )

                        for component in (
                            field.components
                        ):

                            st.write(
                                f"↳ **"
                                f"{component.name}"
                                f"**"
                            )

                            component_details = []

                            if component.data_type:

                                component_details.append(
                                    f"Type: "
                                    f"{component.data_type}"
                                )

                            if component.options:

                                component_details.append(
                                    "Options: "
                                    + " / ".join(
                                        component.options
                                    )
                                )

                            if component.condition:

                                component_details.append(
                                    f"Condition: "
                                    f"{component.condition}"
                                )

                            if component_details:

                                st.caption(
                                    " | ".join(
                                        component_details
                                    )
                                )

                    # ---------------------
                    # Description
                    # ---------------------

                    if field.description:

                        st.write(
                            field.description
                        )

                    # ---------------------
                    # Source Evidence
                    # ---------------------

                    if field.source_text:

                        with st.expander(
                            "Source Evidence",
                            expanded=False,
                        ):

                            st.caption(
                                field.source_text
                            )

        # =================================
        # REPORT INSTRUCTIONS
        # =================================

        if requirement.report_instructions:

            with st.expander(
                "📌 Report Instructions",
                expanded=False,
            ):

                for instruction in (
                    requirement.report_instructions
                ):

                    st.write(
                        f"- {instruction}"
                    )

        # =================================
        # EXTRACTION NOTES
        # =================================

        if requirement.extraction_notes:

            with st.expander(
                "⚠️ Extraction Notes",
                expanded=False,
            ):

                for note in (
                    requirement.extraction_notes
                ):

                    st.write(
                        f"- {note}"
                    )

        # =================================
        # CONFIRMATION
        # =================================

        st.divider()

        left_col, right_col = (
            st.columns(2)
        )

        # ---------------------------------
        # Re-analyze
        # ---------------------------------

        with left_col:

            if st.button(
                "🔄 重新分析",
                use_container_width=True,
                key="reanalyze_cdc_requirement",
            ):

                st.session_state.pop(
                    "cdc_report_requirement_draft",
                    None,
                )

                st.rerun()

        # ---------------------------------
        # Confirm JSON for Page 4
        # ---------------------------------

        with right_col:

            if st.button(
                "✅ 確認需求並進入 IG 比對",
                type="primary",
                use_container_width=True,
                key="confirm_cdc_requirement",
            ):

                # -----------------------------
                # Final Confirmed JSON
                # -----------------------------

                confirmed_requirement_json = (
                    requirement.model_dump(
                        mode="json"
                    )
                )

                # -----------------------------
                # Save Page 4 Input Pack
                # -----------------------------

                st.session_state[
                    "cdc_report_requirement_pack"
                ] = {
                    "source_document": {
                        "file_name":
                            input_pack.get(
                                "file_name"
                            ),

                        "file_type":
                            input_pack.get(
                                "file_type"
                            ),

                        "file_size":
                            input_pack.get(
                                "file_size"
                            ),

                        "created_at":
                            input_pack.get(
                                "created_at"
                            ),
                    },

                    # =========================
                    # PAGE 4 INPUT JSON
                    # =========================

                    "report_requirement":
                        confirmed_requirement_json,

                    "confirmed_at":
                        time.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                }

                # -----------------------------
                # Clear Page 4+ Old Results
                # -----------------------------

                downstream_keys = [
                    "cdc_fhir_mapping",
                    "cdc_fhir_mapping_pack",
                    "cdc_fhir_gap_analysis",
                    "cdc_fhir_gap_analysis_pack",
                    "cdc_fhir_ig_design",
                    "cdc_fhir_ig_design_pack",
                    "cdc_fhir_ig_confirmed_design_pack",
                    "cdc_fsh_output",
                ]

                for key in downstream_keys:

                    st.session_state.pop(
                        key,
                        None,
                    )

                # -----------------------------
                # Go to Page 4
                # -----------------------------

                go_to_kiosk_step(
                    4
                )


# =========================================
# PAGE 4 — EXISTING FHIR IG COMPARISON
# =========================================

if current_step == 4:

    st.subheader(
        "🔎 Existing FHIR IG Comparison"
    )

    # -------------------------------------
    # Load Confirmed Page 3 Requirement
    # -------------------------------------

    requirement_pack = (
        st.session_state.get(
            "cdc_report_requirement_pack"
        )
    )

    if not requirement_pack:

        st.warning(
            "尚未建立已確認的 CDC 通報需求。"
        )

        if st.button(
            "← 返回需求確認",
            use_container_width=True,
            key=(
                "return_to_requirement_"
                "confirmation"
            ),
        ):
            go_to_kiosk_step(
                3
            )

        st.stop()

    requirement_json = (
        requirement_pack.get(
            "report_requirement"
        )
    )

    if not requirement_json:

        st.error(
            "CDC 通報需求資料不存在。"
        )
        st.stop()

    try:

        requirement = (
            CDCReportRequirement.model_validate(
                requirement_json
            )
        )

    except Exception as exc:

        st.error(
            "CDC 通報需求資料格式錯誤。"
        )

        st.exception(
            exc
        )

        st.stop()

    st.success(
        "✓ 已載入 Page 3 確認的 CDC 通報需求"
    )

    # -------------------------------------
    # Current FHIR Knowledge Scope
    # -------------------------------------

    st.markdown(
        "### FHIR Knowledge Scope"
    )

    st.info(
        "FHIR Mapping Agent 將透過 ReAct "
        "先查詢 HTKD 中目前可用的 FHIR packages，"
        "再依 CDC 通報需求決定需要調查的 "
        "Implementation Guide、Profile、Element "
        "與 Terminology evidence。"
    )

    # -------------------------------------
    # Requirement Summary
    # -------------------------------------

    total_fields = sum(
        len(
            section.fields
        )
        for section in requirement.sections
    )

    total_components = sum(
        len(
            field.components
        )
        for section in requirement.sections
        for field in section.fields
    )

    col1, col2, col3 = st.columns(
        3
    )

    with col1:

        st.metric(
            "Sections",
            len(
                requirement.sections
            ),
        )

    with col2:

        st.metric(
            "Fields",
            total_fields,
        )

    with col3:

        st.metric(
            "Components",
            total_components,
        )

    with st.expander(
        "🧩 Confirmed CDC Requirement JSON",
        expanded=False,
    ):

        st.json(
            requirement.model_dump(
                mode="json"
            )
        )

    # -------------------------------------
    # Existing Mapping Result
    # -------------------------------------

    mapping_pack = (
        st.session_state.get(
            "cdc_fhir_mapping_pack"
        )
    )

    mapping = None

    if mapping_pack:

        mapping_json = (
            mapping_pack.get(
                "mapping_result"
            )
        )

        if mapping_json:

            try:

                mapping = (
                    CDCFHIRMappingResult.model_validate(
                        mapping_json
                    )
                )

            except Exception:

                mapping = None

    # -------------------------------------
    # Run Page 4 ReAct Mapping
    # -------------------------------------

    if mapping is None:

        st.markdown(
            "### FHIR Mapping ReAct"
        )

        st.write(
            "Agent 將從已確認的 CDC 通報需求開始，"
            "依需要查詢 HTKD 中的 FHIR evidence。"
        )

        st.caption(
            "流程：Requirement → Reason → "
            "FHIR Tool → Observation → "
            "Mapping Result"
        )

        if st.button(
            "🧠 開始 FHIR Mapping ReAct",
            type="primary",
            use_container_width=True,
            key="run_cdc_fhir_mapping",
        ):

            try:

                with st.status(
                    "正在進行 FHIR Mapping ReAct...",
                    expanded=True,
                ) as status:

                    st.write(
                        "讀取已確認的 CDC 通報需求..."
                    )

                    st.write(
                        "查詢 HTKD FHIR evidence..."
                    )

                    mapping, deps = (
                        map_cdc_report_to_fhir(
                            requirement=requirement,
                            engine=engine,
                            llm_cfg=llm_cfg,
                        )
                    )

                    st.write(
                        "建立結構化 FHIR mapping..."
                    )

                    mapping_json = (
                        mapping.model_dump(
                            mode="json"
                        )
                    )

                    react_evidence = (
                        deps.fhir_evidence
                    )

                    st.session_state[
                        "cdc_fhir_mapping_pack"
                    ] = {
                        "source_requirement": (
                            requirement.model_dump(
                                mode="json"
                            )
                        ),
                        "mapping_result": (
                            mapping_json
                        ),
                        "react_trace": {
                            "fhir_tool_called": (
                                deps.fhir_tool_called
                            ),
                            "fhir_tool_call_count": (
                                deps.fhir_tool_call_count
                            ),
                            "fhir_observation_count": (
                                deps.fhir_observation_count
                            ),
                            "fhir_evidence": (
                                react_evidence
                            ),
                        },
                        "created_at": time.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }

                    status.update(
                        label=(
                            "FHIR Mapping ReAct 完成"
                        ),
                        state="complete",
                        expanded=False,
                    )

                st.rerun()

            except Exception as exc:

                st.error(
                    "FHIR Mapping ReAct 執行失敗。"
                )

                st.exception(
                    exc
                )

        st.stop()

    # -------------------------------------
    # Mapping Completed
    # -------------------------------------

    st.markdown(
        "### Mapping Result"
    )

    react_trace = (
        mapping_pack.get(
            "react_trace",
            {},
        )
        if mapping_pack
        else {}
    )

    col1, col2, col3 = st.columns(
        3
    )

    with col1:

        st.metric(
            "Mappings",
            len(
                mapping.mappings
            ),
        )

    with col2:

        st.metric(
            "FHIR Tool Calls",
            react_trace.get(
                "fhir_tool_call_count",
                0,
            ),
        )

    with col3:

        st.metric(
            "Observations",
            react_trace.get(
                "fhir_observation_count",
                0,
            ),
        )

    # -------------------------------------
    # Packages Actually Consulted
    # -------------------------------------

    st.markdown(
        "#### Packages Consulted"
    )

    if mapping.packages_consulted:

        for package_name in (
            mapping.packages_consulted
        ):

            st.write(
                f"• {package_name}"
            )

    else:

        st.caption(
            "No package information recorded."
        )

    # -------------------------------------
    # Status Summary
    # -------------------------------------

    status_counts = {
        "Covered": 0,
        "Partial": 0,
        "Missing": 0,
        "Needs Investigation": 0,
    }

    for item in mapping.mappings:

        if (
            item.mapping_status
            in status_counts
        ):

            status_counts[
                item.mapping_status
            ] += 1

    cols = st.columns(
        4
    )

    status_order = [
        "Covered",
        "Partial",
        "Missing",
        "Needs Investigation",
    ]

    for col, status_name in zip(
        cols,
        status_order,
    ):

        with col:

            st.metric(
                status_name,
                status_counts[
                    status_name
                ],
            )

    # -------------------------------------
    # Mapping Details
    # -------------------------------------

    st.markdown(
        "#### CDC → FHIR Mapping"
    )

    for index, item in enumerate(
        mapping.mappings,
        start=1,
    ):

        component_label = ""

        if item.component_name:

            component_label = (
                f" / {item.component_name}"
            )

        title = (
            f"{index}. "
            f"{item.section} / "
            f"{item.field_name}"
            f"{component_label}"
            f" — {item.mapping_status}"
        )

        with st.expander(
            title,
            expanded=False,
        ):

            if item.fhir_resource:

                st.write(
                    "**FHIR Resource:** "
                    f"{item.fhir_resource}"
                )

            st.write(
                "**Mapping Explanation:**"
            )

            st.write(
                item.mapping_explanation
            )

            if item.fhir_elements:

                st.write(
                    "**FHIR Evidence:**"
                )

                for evidence in (
                    item.fhir_elements
                ):

                    st.code(
                        evidence.element_path
                    )

                    evidence_details = {
                        "package_name": (
                            evidence.package_name
                        ),
                        "package_version": (
                            evidence.package_version
                        ),
                        "artifact_id": (
                            evidence.artifact_id
                        ),
                        "artifact_url": (
                            evidence.artifact_url
                        ),
                        "min_cardinality": (
                            evidence.min_cardinality
                        ),
                        "max_cardinality": (
                            evidence.max_cardinality
                        ),
                        "type_codes": (
                            evidence.type_codes
                        ),
                        "target_profiles": (
                            evidence.target_profiles
                        ),
                        "binding_strength": (
                            evidence.binding_strength
                        ),
                        "binding_value_set": (
                            evidence.binding_value_set
                        ),
                    }

                    st.json(
                        evidence_details
                    )

            if item.terminology:

                st.write(
                    "**Terminology Evidence:**"
                )

                for terminology in (
                    item.terminology
                ):

                    st.json(
                        terminology.model_dump(
                            mode="json"
                        )
                    )

            if item.unresolved_questions:

                st.write(
                    "**Unresolved Questions:**"
                )

                for question in (
                    item.unresolved_questions
                ):

                    st.write(
                        f"• {question}"
                    )

    # -------------------------------------
    # Analysis Notes
    # -------------------------------------

    if mapping.analysis_notes:

        with st.expander(
            "📝 Analysis Notes",
            expanded=False,
        ):

            for note in (
                mapping.analysis_notes
            ):

                st.write(
                    f"• {note}"
                )

    # -------------------------------------
    # Operational ReAct Evidence
    # -------------------------------------

    with st.expander(
        "🔧 ReAct Operational Evidence",
        expanded=False,
    ):

        st.caption(
            "顯示 tool calls 與 observations，"
            "不顯示模型私有推理內容。"
        )

        st.json(
            react_trace
        )

    # -------------------------------------
    # Structured Mapping JSON
    # -------------------------------------

    with st.expander(
        "🧩 FHIR Mapping JSON",
        expanded=False,
    ):

        st.json(
            mapping.model_dump(
                mode="json"
            )
        )

    # -------------------------------------
    # Navigation
    # -------------------------------------

    st.divider()

    nav_left, nav_middle, nav_right = (
        st.columns(
            [1, 1, 1]
        )
    )

    with nav_left:

        if st.button(
            "← 返回需求確認",
            use_container_width=True,
            key="page4_back",
        ):

            go_to_kiosk_step(
                3
            )

    with nav_middle:

        if st.button(
            "🔄 重新分析",
            use_container_width=True,
            key="page4_reanalyze",
        ):

            st.session_state.pop(
                "cdc_fhir_mapping_pack",
                None,
            )

            st.session_state.pop(
                "cdc_fhir_gap_analysis_pack",
                None,
            )

            st.session_state.pop(
                "cdc_fhir_ig_design_pack",
                None,
            )

            st.session_state.pop(
                "cdc_fhir_ig_confirmed_design_pack",
                None,
            )

            st.session_state.pop(
                "cdc_fsh_output",
                None,
            )

            st.rerun()

    with nav_right:

        if st.button(
            "確認 Mapping 並進入 Gap / ReAct →",
            type="primary",
            use_container_width=True,
            key="page4_confirm_mapping",
        ):

            go_to_kiosk_step(
                5
            )

# =========================================
# PAGE 5 — GAP ANALYSIS / REACT
# =========================================

if current_step == 5:

    st.subheader(
        "🧠 Gap Analysis / ReAct"
    )

    # -------------------------------------
    # Load Page 4 IG Comparison Result
    # -------------------------------------

    mapping_pack = (
        st.session_state.get(
            "cdc_fhir_mapping_pack"
        )
    )

    if not mapping_pack:

        st.warning(
            "尚未完成 Existing FHIR IG Comparison。"
        )

        if st.button(
            "← 返回 IG 比對",
            use_container_width=True,
            key="return_to_ig_comparison_empty",
        ):
            go_to_kiosk_step(
                4
            )

        st.stop()

    # -------------------------------------
    # Processing Status
    # -------------------------------------

    st.markdown(
        "### 處理狀態"
    )

    st.write(
        "✓ Existing FHIR IG Comparison 已載入"
    )

    st.info(
        "本階段將針對 Page 4 發現的 "
        "Partial、Missing 或 Needs Investigation "
        "項目進行 ReAct 分析。"
    )

    # -------------------------------------
    # Future ReAct Capabilities
    # -------------------------------------

    st.markdown(
        "### ReAct Investigation"
    )

    st.write(
        "後續將由 FHIR IG Design Agent "
        "依實際 Gap 決定需要使用的工具。"
    )

    st.markdown(
        """
- Inspect FHIR R4
- Inspect TW Core
- Inspect TWIDIR
- Inspect existing profiles
- Inspect terminology
- Query HTKD when terminology evidence is required
"""
    )

    # -------------------------------------
    # Temporary Development Placeholder
    # -------------------------------------

    st.warning(
        "FHIR IG Design Agent / ReAct "
        "尚未實作。"
    )

    # -------------------------------------
    # Navigation
    # -------------------------------------

    st.divider()

    if st.button(
        "← 返回 IG 比對",
        use_container_width=True,
        key="return_to_ig_comparison",
    ):
        go_to_kiosk_step(
            4
        )


# =========================================
# PAGE 6 — IG DESIGN CONFIRMATION
# =========================================

if current_step == 6:

    st.subheader(
        "🧩 FHIR IG 設計確認"
    )

    # -------------------------------------
    # Load Page 5 Design Result
    # -------------------------------------

    design_pack = (
        st.session_state.get(
            "cdc_fhir_ig_design_pack"
        )
    )

    if not design_pack:

        st.warning(
            "尚未建立 FHIR IG Design Proposal。"
        )

        if st.button(
            "← 返回 Gap / ReAct",
            use_container_width=True,
            key="return_to_gap_analysis_empty",
        ):
            go_to_kiosk_step(
                5
            )

        st.stop()

    # -------------------------------------
    # Design Status
    # -------------------------------------

    st.write(
        "✓ FHIR IG Design Proposal 已載入"
    )

    st.caption(
        "請確認 ReAct 分析後提出的 "
        "FHIR IG 設計內容。"
    )

    # -------------------------------------
    # Future Design Review UI
    # -------------------------------------

    st.markdown(
        "### Proposed Design"
    )

    st.info(
        "後續將在此顯示每一項 CDC 通報需求的"
        "最終 FHIR 設計建議，例如："
        "Reuse Existing Profile、Constraint、"
        "New Profile、Extension、ValueSet "
        "或 CodeSystem。"
    )

    # -------------------------------------
    # Temporary Development Placeholder
    # -------------------------------------

    st.warning(
        "FHIR IG Design Confirmation UI "
        "尚未實作。"
    )

    # -------------------------------------
    # Navigation
    # -------------------------------------

    st.divider()

    if st.button(
        "← 返回 Gap / ReAct",
        use_container_width=True,
        key="return_to_gap_analysis",
    ):
        go_to_kiosk_step(
            5
        )


# =========================================
# PAGE 7 — FSH GENERATION
# =========================================

if current_step == 7:

    st.subheader(
        "🧬 FSH Generation"
    )

    # -------------------------------------
    # Load Confirmed IG Design
    # -------------------------------------

    confirmed_design_pack = (
        st.session_state.get(
            "cdc_fhir_ig_confirmed_design_pack"
        )
    )

    if not confirmed_design_pack:

        st.warning(
            "尚未完成 FHIR IG 設計確認。"
        )

        if st.button(
            "← 返回設計確認",
            use_container_width=True,
            key="return_to_design_confirmation_empty",
        ):
            go_to_kiosk_step(
                6
            )

        st.stop()

    # -------------------------------------
    # Design Status
    # -------------------------------------

    st.write(
        "✓ Confirmed FHIR IG Design 已載入"
    )

    st.caption(
        "FSH 將由已確認的結構化 IG Design "
        "產生，而不是直接由 LLM 自由產生。"
    )

    # -------------------------------------
    # Future FSH Output
    # -------------------------------------

    st.markdown(
        "### Generated FSH"
    )

    st.info(
        "後續將在此產生 Profile、Extension、"
        "ValueSet、CodeSystem 與 Example "
        "所需的 FSH。"
    )

    # -------------------------------------
    # Temporary Development Placeholder
    # -------------------------------------

    st.warning(
        "FSH Generator 尚未實作。"
    )

    # -------------------------------------
    # Navigation
    # -------------------------------------

    st.divider()

    if st.button(
        "← 返回設計確認",
        use_container_width=True,
        key="return_to_design_confirmation",
    ):
        go_to_kiosk_step(
            6
        )

