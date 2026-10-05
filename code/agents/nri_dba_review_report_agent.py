 # py code beginning

from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent

from models.nri_dba_review_report_models import (
    DBAReviewReport,
)

from nri_ai_core.ai_runtime import (
    build_agent_model,
)


# =============================================================================
# AGENT INSTRUCTIONS
# =============================================================================

DBA_REVIEW_REPORT_AGENT_INSTRUCTIONS = """
You are the NRI Enterprise DBA Review Report Writer.

PURPOSE
Transform an already completed DBA design review into a professional,
clear narrative report suitable for an A4 PDF.

IMPORTANT
- Do not perform a new technical review.
- Do not add new technical findings.
- Do not invent tables, columns, PKs, FKs, constraints, or other facts.
- Do not change the conclusions of the supplied DBA review.
- Preserve the distinction between SOURCE FACT, OBSERVED ENTERPRISE
  EVIDENCE, and DBA RECOMMENDATION.
- Prefer narrative sections and concise bullets over complex tables.
- SQL constraints and physical identifiers may be preserved verbatim.
- Use Traditional Chinese.

Useful sections may include:
Executive Summary, Design Assessment, Key DBA Findings,
Constraint Recommendations, Enterprise Control Recommendations,
Priority Actions, and Final Recommendation.

Omit a section when the supplied review contains no supporting content.
"""


# =============================================================================
# AGENT FACTORY
# =============================================================================

def create_dba_review_report_agent(
    model,
) -> Agent:
    return Agent(
        model=model,
        output_type=DBAReviewReport,
        instructions=(
            DBA_REVIEW_REPORT_AGENT_INSTRUCTIONS
        ),
    )


# =============================================================================
# MODEL SETTINGS
# =============================================================================

def _agent_model_settings(
    llm_cfg: dict[str, Any],
) -> dict:
    settings = {
        "temperature": float(
            llm_cfg.get(
                "temperature",
                0.0,
            )
            or 0.0
        ),
    }

    num_predict = int(
        llm_cfg.get(
            "num_predict",
            0,
        )
        or 0
    )

    if num_predict > 0:
        settings[
            "max_tokens"
        ] = num_predict

    return settings


# =============================================================================
# AGENT EXECUTION
# =============================================================================

def run_dba_review_report_agent(
    *,
    target_db: str,
    design_obj: dict,
    review_obj: dict,
    llm_cfg: dict,
) -> dict:
    """
    Generate the narrative DBA Design Review report.

    The technical DBA review has already been completed by the
    DBA Design Review Agent.

    This Agent does not investigate the database and does not
    perform another technical review. Its responsibility is to
    transform the completed structured review into a professional
    report suitable for presentation and PDF rendering.
    """

    # -------------------------------------------------------------------------
    # Validate LLM Runtime
    # -------------------------------------------------------------------------

    if (
        not llm_cfg
        or not llm_cfg.get(
            "enabled"
        )
    ):
        raise RuntimeError(
            "LLM backend is disabled."
        )

    # -------------------------------------------------------------------------
    # Build Model
    # -------------------------------------------------------------------------

    model = build_agent_model(
        llm_cfg
    )

    # -------------------------------------------------------------------------
    # Create Report Agent
    # -------------------------------------------------------------------------

    agent = (
        create_dba_review_report_agent(
            model
        )
    )

    # -------------------------------------------------------------------------
    # Build Report Context
    # -------------------------------------------------------------------------
    #
    # IMPORTANT:
    #
    # This Agent receives the completed technical review.
    #
    # It does NOT receive database tools because it is not responsible
    # for performing another investigation.
    #
    # -------------------------------------------------------------------------

    report_context = {
        "reference_database": (
            target_db
        ),
        "proposed_table": (
            design_obj
        ),
        "dba_review": (
            review_obj
        ),
    }

    # -------------------------------------------------------------------------
    # Report Prompt
    # -------------------------------------------------------------------------

    prompt = (
        "Write the NRI Enterprise DBA Design Review report "
        "from the completed review below.\n\n"

        "The DBA technical review has already been completed. "
        "Do not perform another technical review, add findings, "
        "or change its conclusions.\n\n"

        "Transform the supplied structured review into a clear "
        "professional report suitable for an A4 PDF.\n\n"

        "COMPLETED DBA REVIEW CONTEXT:\n"
        + json.dumps(
            report_context,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    # -------------------------------------------------------------------------
    # Run Report Agent
    # -------------------------------------------------------------------------

    result = agent.run_sync(
        prompt,
        model_settings=(
            _agent_model_settings(
                llm_cfg
            )
        ),
    )

    # -------------------------------------------------------------------------
    # Return Structured Report
    # -------------------------------------------------------------------------

    return (
        result.output.model_dump()
    )


