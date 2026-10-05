 # py code beginning

"""Clinical Review UI.

Domain-specific presentation helpers for the
HTKD Clinical Case Review application.

This module is responsible only for presentation.

It does not:
- perform clinical reasoning
- call LLMs
- call HTKD tools
- query databases
- decide which ReAct action to execute

Page 4 performs the Clinical Review Agent run.
This module displays the resulting Page 3 and
Page 4 data.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from nri_code_core.ui.result_ui import (
    render_inline_list,
    render_json_result,
    render_key_value_grid,
    render_list_section,
    render_record_table,
    render_section_header,
    render_status,
)


# =========================================
# SMALL HELPERS
# =========================================

def _as_list(
    value: Any,
) -> list[Any]:
    """
    Normalize a value into a list.
    """

    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):
        return value

    return [
        value
    ]


def _dict_list(
    value: Any,
) -> list[dict[str, Any]]:
    """
    Normalize a value into a list of
    dictionaries.
    """

    values = _as_list(
        value
    )

    return [
        item
        for item in values
        if isinstance(
            item,
            dict,
        )
    ]


# =========================================
# PAGE 3
# PREPARED CLINICAL CASE
# =========================================

def render_prepared_clinical_case(
    preparation_pack: dict[str, Any],
) -> None:
    """
    Render the PreparedClinicalCase produced
    by the Page 3 preparation agent.
    """

    prepared_case = (
        preparation_pack.get(
            "prepared_case",
            {},
        )
        or {}
    )

    if not prepared_case:

        render_status(
            "尚未取得 PreparedClinicalCase。",
            status="info",
        )

        return

    render_section_header(
        "Prepared Clinical Case",
        (
            "Page 3 Clinical Case Preparation "
            "Agent 所建立的結構化案例資料。"
        ),
    )

    # -------------------------------------
    # BASIC INFORMATION
    # -------------------------------------

    basic_information = [
        (
            "年齡",
            prepared_case.get(
                "age"
            ),
        ),
        (
            "性別",
            prepared_case.get(
                "sex"
            ),
        ),
    ]

    render_key_value_grid(
        basic_information
    )

    # -------------------------------------
    # CHIEF COMPLAINT
    # -------------------------------------

    st.markdown(
        "#### 📌 主訴"
    )

    render_inline_list(
        prepared_case.get(
            "chief_complaint"
        )
    )

    # -------------------------------------
    # CURRENT FINDINGS
    # -------------------------------------

    st.markdown(
        "#### 🔎 目前臨床資訊"
    )

    current_findings = (
        prepared_case.get(
            "current_findings",
            [],
        )
        or []
    )

    if current_findings:

        render_record_table(
            current_findings
        )

    else:

        st.caption(
            "未提供"
        )

    # -------------------------------------
    # NEGATIVE FINDINGS
    # -------------------------------------

    render_list_section(
        "未出現 / 否定資訊",
        prepared_case.get(
            "negative_findings"
        ),
    )

    # -------------------------------------
    # MEDICAL HISTORY
    # -------------------------------------

    render_list_section(
        "相關病史",
        prepared_case.get(
            "medical_history"
        ),
    )

    # -------------------------------------
    # MEDICATIONS
    # -------------------------------------

    st.markdown(
        "#### 💊 用藥資訊"
    )

    medications = (
        prepared_case.get(
            "medications",
            [],
        )
        or []
    )

    if medications:

        render_record_table(
            medications
        )

    else:

        st.caption(
            "未提供"
        )

    # -------------------------------------
    # ALLERGIES
    # -------------------------------------

    render_list_section(
        "過敏資訊",
        prepared_case.get(
            "allergies"
        ),
    )

    # -------------------------------------
    # LAB / VITAL
    # -------------------------------------

    render_list_section(
        "檢驗 / 生命徵象",
        prepared_case.get(
            "laboratory_and_vitals"
        ),
    )

    # -------------------------------------
    # MISSING INFORMATION
    # -------------------------------------

    render_list_section(
        "尚缺資訊",
        prepared_case.get(
            "missing_information"
        ),
    )

    # -------------------------------------
    # PII STATUS
    # -------------------------------------

    pii = (
        prepared_case.get(
            "pii",
            {},
        )
        or {}
    )

    st.markdown(
        "#### 🔐 個人識別資訊"
    )

    pii_detected = bool(
        pii.get(
            "detected",
            False,
        )
    )

    if pii_detected:

        render_status(
            "偵測到個人識別資訊，"
            "準備階段已進行處理。",
            status="warning",
        )

    else:

        render_status(
            "未偵測到需處理的個人識別資訊。",
            status="success",
        )

    removed_types = (
        pii.get(
            "removed_types",
            [],
        )
        or []
    )

    if removed_types:

        render_list_section(
            "已移除 / 遮罩類型",
            removed_types,
        )


# =========================================
# WHO REACT OBSERVATIONS
# =========================================

def get_who_react_observations(
    review_pack: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Return the actual WHO ICD observations
    collected during the Clinical Review
    Agent ReAct run.

    Page 4 stores these under:

        review_pack["who_evidence"]

    Each entry represents an actual tool
    observation.
    """

    observations = (
        review_pack.get(
            "who_evidence",
            [],
        )
        or []
    )

    if isinstance(
        observations,
        dict,
    ):
        observations = [
            observations
        ]

    return [
        item
        for item in observations
        if isinstance(
            item,
            dict,
        )
    ]


# =========================================
# WHO FOUNDATION
# =========================================

def render_who_foundation(
    review_pack: dict[str, Any],
) -> None:
    """
    Render WHO ICD Foundation observations
    returned by ReAct tool execution.
    """

    observations = (
        get_who_react_observations(
            review_pack
        )
    )

    foundation_records: list[
        dict[str, Any]
    ] = []

    # -------------------------------------
    # READ ACTUAL REACT OBSERVATIONS
    # -------------------------------------

    for observation in observations:

        action = (
            observation.get(
                "action"
            )
        )

        # ---------------------------------
        # SEARCH OBSERVATION
        #
        # search_who_icd()
        # ---------------------------------

        if action == "search_who_icd":

            clinical_concept = (
                observation.get(
                    "clinical_concept"
                )
            )

            records = _dict_list(
                observation.get(
                    "records"
                )
            )

            for record in records:

                display_record = dict(
                    record
                )

                if clinical_concept:

                    display_record[
                        "clinical_concept"
                    ] = clinical_concept

                foundation_records.append(
                    display_record
                )

        # ---------------------------------
        # DETAILED EVIDENCE OBSERVATION
        #
        # get_who_icd_evidence_by_uri()
        # ---------------------------------

        elif (
            action
            == "get_who_icd_evidence"
        ):

            evidence = (
                observation.get(
                    "evidence"
                )
            )

            if not isinstance(
                evidence,
                dict,
            ):
                continue

            foundation = (
                evidence.get(
                    "foundation"
                )
            )

            if isinstance(
                foundation,
                dict,
            ):

                foundation_records.append(
                    foundation
                )

            elif isinstance(
                foundation,
                list,
            ):

                foundation_records.extend(
                    item
                    for item in foundation
                    if isinstance(
                        item,
                        dict,
                    )
                )

    # -------------------------------------
    # DISPLAY
    # -------------------------------------

    render_section_header(
        "WHO ICD Foundation",
        (
            "HTKD WHO ICD Foundation "
            "terminology evidence retrieved "
            "by the Clinical Review Agent."
        ),
    )

    if not foundation_records:

        render_status(
            (
                "本次 ReAct 尚無 WHO ICD "
                "Foundation 查詢結果。"
            ),
            status="info",
        )

        return

    render_record_table(
        foundation_records
    )


# =========================================
# WHO ICD-11 MMS
# =========================================

def render_who_mms(
    review_pack: dict[str, Any],
) -> None:
    """
    Render WHO ICD-11 MMS evidence returned
    through detailed WHO ReAct observations.
    """

    observations = (
        get_who_react_observations(
            review_pack
        )
    )

    mms_records: list[
        dict[str, Any]
    ] = []

    # -------------------------------------
    # READ ACTUAL REACT OBSERVATIONS
    # -------------------------------------

    for observation in observations:

        action = (
            observation.get(
                "action"
            )
        )

        if (
            action
            != "get_who_icd_evidence"
        ):
            continue

        evidence = (
            observation.get(
                "evidence"
            )
        )

        if not isinstance(
            evidence,
            dict,
        ):
            continue

        # ---------------------------------
        # MMS
        # ---------------------------------

        mms = (
            evidence.get(
                "mms"
            )
        )

        if isinstance(
            mms,
            dict,
        ):

            mms_records.append(
                mms
            )

        elif isinstance(
            mms,
            list,
        ):

            mms_records.extend(
                item
                for item in mms
                if isinstance(
                    item,
                    dict,
                )
            )

        # ---------------------------------
        # MMS CHILDREN
        # ---------------------------------

        mms_children = (
            evidence.get(
                "mms_children"
            )
        )

        if isinstance(
            mms_children,
            dict,
        ):

            mms_records.append(
                mms_children
            )

        elif isinstance(
            mms_children,
            list,
        ):

            mms_records.extend(
                item
                for item in mms_children
                if isinstance(
                    item,
                    dict,
                )
            )

    # -------------------------------------
    # DISPLAY
    # -------------------------------------

    render_section_header(
        "WHO ICD-11 MMS",
        (
            "WHO ICD-11 Mortality and "
            "Morbidity Statistics evidence "
            "retrieved from HTKD."
        ),
    )

    if not mms_records:

        render_status(
            (
                "本次 ReAct 尚無 WHO ICD-11 "
                "MMS 查詢結果。"
            ),
            status="info",
        )

        return

    render_record_table(
        mms_records
    )


# =========================================
# FUTURE CAPABILITY
# =========================================

def render_future_capability(
    *,
    title: str,
    records: Any,
) -> None:
    """
    Render a future Clinical Review
    capability such as Taiwan ICD,
    medication, HIS, or SOP evidence.
    """

    render_section_header(
        title
    )

    values = _as_list(
        records
    )

    if not values:

        st.caption(
            "尚未取得資料。"
        )

        return

    dict_records = [
        item
        for item in values
        if isinstance(
            item,
            dict,
        )
    ]

    if dict_records:

        render_record_table(
            dict_records
        )

        return

    for item in values:

        st.write(
            item
        )


# =========================================
# CLINICAL REVIEW RESULT
# =========================================

def render_clinical_review_result(
    review_pack: dict[str, Any],
) -> None:
    """
    Render the final structured output
    produced by the Clinical Review Agent.
    """

    review = (
        review_pack.get(
            "review",
            {},
        )
        or {}
    )

    render_section_header(
        "Clinical Review",
        (
            "Clinical Review Agent "
            "structured output."
        ),
    )

    if not review:

        render_status(
            "尚未取得 Clinical Review 結果。",
            status="info",
        )

        return

    # -------------------------------------
    # REVIEW SUMMARY
    # -------------------------------------

    review_summary = (
        review.get(
            "review_summary"
        )
    )

    if review_summary:

        st.markdown(
            "#### Review Summary"
        )

        st.write(
            review_summary
        )

    # -------------------------------------
    # REVIEWED CASE CONCEPTS
    # -------------------------------------

    reviewed_case_concepts = (
        review.get(
            "reviewed_case_concepts",
            [],
        )
        or []
    )

    if reviewed_case_concepts:

        render_list_section(
            "Reviewed Case Concepts",
            reviewed_case_concepts,
        )

    # -------------------------------------
    # UNRESOLVED QUESTIONS
    # -------------------------------------

    unresolved_questions = (
        review.get(
            "unresolved_questions",
            [],
        )
        or []
    )

    if unresolved_questions:

        render_list_section(
            "Unresolved Questions",
            unresolved_questions,
        )

    # -------------------------------------
    # FALLBACK
    #
    # If the model evolves and adds fields,
    # preserve visibility of the complete
    # structured result.
    # -------------------------------------

    known_fields = {
        "review_summary",
        "reviewed_case_concepts",
        "unresolved_questions",
    }

    extra_fields = {
        key: value
        for key, value in review.items()
        if key not in known_fields
    }

    if extra_fields:

        st.markdown(
            "#### Additional Review Data"
        )

        render_json_result(
            extra_fields
        )


# =========================================
# REACT TRACE
# =========================================

def render_react_trace(
    review_pack: dict[str, Any],
) -> None:
    """
    Render operational ReAct information.

    This displays tool execution facts only.
    It does not expose private model
    reasoning.
    """

    trace = (
        review_pack.get(
            "agent_trace",
            {},
        )
        or {}
    )

    render_section_header(
        "ReAct Tool Trace",
        (
            "Operational tool execution "
            "information from the Clinical "
            "Review Agent."
        ),
    )

    if not trace:

        st.caption(
            "尚無 ReAct tool trace。"
        )

        return

    who_tool_called = bool(
        trace.get(
            "who_tool_called",
            False,
        )
    )

    if who_tool_called:

        render_status(
            "WHO ICD Tool 已由 Agent 呼叫。",
            status="success",
        )

    else:

        render_status(
            "本次 Agent 未呼叫 WHO ICD Tool。",
            status="info",
        )

    trace_values = [
        (
            "WHO Tool Called",
            who_tool_called,
        ),
        (
            "WHO Tool Call Count",
            trace.get(
                "who_tool_call_count",
                0,
            ),
        ),
        (
            "WHO Observation Count",
            trace.get(
                "who_observation_count",
                0,
            ),
        ),
    ]

    render_key_value_grid(
        trace_values
    )


# =========================================
# MAIN PAGE 5 RENDERER
# =========================================

def render_clinical_case_review(
    *,
    preparation_pack: dict[str, Any],
    review_pack: dict[str, Any],
) -> None:
    """
    Render the complete Page 5 Clinical
    Case Review result.
    """

    # =====================================
    # PAGE 3 RESULT
    # =====================================

    render_prepared_clinical_case(
        preparation_pack
    )

    st.divider()

    # =====================================
    # WHO FOUNDATION
    # =====================================

    render_who_foundation(
        review_pack
    )

    st.divider()

    # =====================================
    # WHO ICD-11 MMS
    # =====================================

    render_who_mms(
        review_pack
    )

    st.divider()

    # =====================================
    # TAIWAN ICD
    # FUTURE REACT CAPABILITY
    # =====================================

    render_future_capability(
        title="Taiwan ICD",
        records=review_pack.get(
            "tw_icd"
        ),
    )

    st.divider()

    # =====================================
    # MEDICATION
    # FUTURE REACT CAPABILITY
    # =====================================

    render_future_capability(
        title="Medication Knowledge",
        records=review_pack.get(
            "medication"
        ),
    )

    st.divider()

    # =====================================
    # HIS
    # FUTURE REACT CAPABILITY
    # =====================================

    render_future_capability(
        title="HIS Evidence",
        records=review_pack.get(
            "his"
        ),
    )

    st.divider()

    # =====================================
    # SOP
    # FUTURE REACT CAPABILITY
    # =====================================

    render_future_capability(
        title="SOP / Guideline Evidence",
        records=review_pack.get(
            "sop"
        ),
    )

    st.divider()

    # =====================================
    # CLINICAL REVIEW RESULT
    # =====================================

    render_clinical_review_result(
        review_pack
    )

    st.divider()

    # =====================================
    # REACT TRACE
    # =====================================

    render_react_trace(
        review_pack
    )

