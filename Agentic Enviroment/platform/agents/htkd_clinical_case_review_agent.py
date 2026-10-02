 # py code beginning

"""HTKD Clinical Case Review Agent.

ReAct pattern:

Clinical Review Agent
    ↓
Reason / decide what evidence is needed
    ↓
Call available tool when needed
    ↓
Observe tool result
    ↓
Continue reasoning
    ↓
Return structured review result

WHO ICD is one capability available to the agent.
Future capabilities may include Taiwan ICD, medication,
HIS, SOP, and guideline evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import (
    Agent,
    RunContext,
)

from sqlalchemy.engine import Engine

from nri_ai_core.ai_runtime import (
    build_agent_model,
)

from htkd.db.who_icd import (
    get_who_icd_evidence,
    search_foundation,
)

from models.htkd_clinical_case_review_models import (
    ClinicalCaseReviewResult,
)


# =========================================
# CLINICAL REVIEW DEPENDENCIES
# =========================================

@dataclass
class HTKDClinicalReviewDeps:
    """
    Runtime dependencies and tool observations
    for the Clinical Review Agent.

    This follows the same pattern as the
    LilyLab ecotourism ReAct dependencies.
    """

    # -------------------------------------
    # Runtime dependency
    # -------------------------------------

    engine: Engine

    # -------------------------------------
    # WHO ICD tool trace
    # -------------------------------------

    who_tool_called: bool = False

    who_tool_call_count: int = 0

    who_observation_count: int = 0

    # -------------------------------------
    # WHO ICD observations
    #
    # A clinical case may require more than
    # one WHO lookup, so observations are
    # accumulated rather than overwritten.
    # -------------------------------------

    who_evidence: list[
        dict[str, Any]
    ] = field(
        default_factory=list
    )


# =========================================
# CREATE CLINICAL REVIEW AGENT
# =========================================

def create_htkd_clinical_case_review_agent(
    llm_cfg: dict[str, Any],
) -> Agent:
    """
    Create the Clinical Review ReAct Agent.

    The agent receives a PreparedClinicalCase.

    The agent decides whether WHO ICD evidence
    is needed and calls the WHO ICD tool when
    appropriate.

    Page 4 does not decide which clinical
    concepts should be searched.
    """

    model = build_agent_model(
        llm_cfg
    )

    agent = Agent(
        model=model,
        deps_type=HTKDClinicalReviewDeps,
        output_type=ClinicalCaseReviewResult,
        instructions=(
            "You are a Clinical Review Agent. "

            "You receive a PreparedClinicalCase "
            "containing clinical information that "
            "has already been prepared and "
            "de-identified. "

            "Review the explicit clinical information "
            "in the case and decide what supporting "
            "evidence is useful. "

            "When WHO ICD terminology evidence is "
            "useful for reviewing an explicit clinical "
            "concept, use the WHO ICD tool. "

            "The WHO ICD tool accepts a concise "
            "English clinical concept. "

            "You may call the WHO ICD tool more than "
            "once when different explicit clinical "
            "concepts require evidence. "

            "Use the observations returned by tools "
            "to decide what to do next. "

            "Do not call tools merely because they "
            "exist. Call a tool when its evidence is "
            "useful for the current case. "

            "Base WHO ICD statements only on evidence "
            "returned by the WHO ICD tool. "

            "Do not invent WHO ICD codes, titles, "
            "URIs, classifications, or relationships. "

            "WHO terminology evidence does not by "
            "itself establish the patient's diagnosis. "

            "Do not infer a subtype, severity, "
            "complication, or other clinical fact "
            "that is not supported by the case. "

            "Do not provide treatment recommendations. "

            "Preserve uncertainty when the available "
            "case information is insufficient. "

            "When sufficient evidence has been "
            "collected, return the structured "
            "ClinicalCaseReviewResult."
        ),
    )

    # =====================================
    # WHO ICD TOOL 1
    # SEARCH WHO FOUNDATION
    # =====================================

    @agent.tool
    def search_who_icd(
        ctx: RunContext[
            HTKDClinicalReviewDeps
        ],
        clinical_concept: str,
    ) -> list[dict[str, Any]]:
        """
        Search WHO ICD Foundation for an
        explicit clinical concept.

        Use a concise English clinical term.

        Search results are terminology
        candidates, not confirmed diagnoses.
        """

        # ---------------------------------
        # RECORD TOOL CALL
        # ---------------------------------

        ctx.deps.who_tool_called = True
        ctx.deps.who_tool_call_count += 1

        # ---------------------------------
        # SEARCH WHO FOUNDATION
        # ---------------------------------

        records = search_foundation(
            engine=ctx.deps.engine,
            query=clinical_concept,
            language="en",
            limit=10,
        )

        # ---------------------------------
        # PRESERVE OBSERVATION
        # ---------------------------------

        observation = {
            "action": "search_who_icd",
            "clinical_concept":
                clinical_concept,
            "records":
                records,
        }

        ctx.deps.who_evidence.append(
            observation
        )

        ctx.deps.who_observation_count = (
            len(
                ctx.deps.who_evidence
            )
        )

        # ---------------------------------
        # RETURN OBSERVATION TO AGENT
        # ---------------------------------

        return records


    # =====================================
    # WHO ICD TOOL 2
    # GET DETAILED WHO EVIDENCE
    # =====================================

    @agent.tool
    def get_who_icd_evidence_by_uri(
        ctx: RunContext[
            HTKDClinicalReviewDeps
        ],
        foundation_uri: str,
    ) -> dict[str, Any] | None:
        """
        Retrieve detailed WHO ICD evidence
        for a Foundation URI.

        The foundation_uri should come from
        an actual WHO Foundation search
        observation.
        """

        # ---------------------------------
        # RECORD TOOL CALL
        # ---------------------------------

        ctx.deps.who_tool_called = True
        ctx.deps.who_tool_call_count += 1

        # ---------------------------------
        # RETRIEVE WHO EVIDENCE
        # ---------------------------------

        evidence = get_who_icd_evidence(
            engine=ctx.deps.engine,
            foundation_uri=foundation_uri,
            language="en",
            include_mms_children=True,
        )

        # ---------------------------------
        # PRESERVE OBSERVATION
        # ---------------------------------

        observation = {
            "action":
                "get_who_icd_evidence",

            "foundation_uri":
                foundation_uri,

            "evidence":
                evidence,
        }

        ctx.deps.who_evidence.append(
            observation
        )

        ctx.deps.who_observation_count = (
            len(
                ctx.deps.who_evidence
            )
        )

        # ---------------------------------
        # RETURN OBSERVATION TO AGENT
        # ---------------------------------

        return evidence

    # =====================================
    # RETURN AGENT
    # =====================================

    return agent

