 # py code beginning

from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent

from models.nri_dba_design_document_models import (
    DesignDocumentInterpretation,
)

from nri_ai_core.ai_runtime import (
    build_agent_model,
)


DESIGN_DOCUMENT_AGENT_INSTRUCTIONS = """
You are the NRI Enterprise Database Design Document Agent.

ROLE
Interpret an enterprise database design specification supplied by the
application and convert it into a conservative structured design object.

RULES
- Use only the supplied source document content.
- Do not invent a schema name when the source does not provide one.
- Preserve physical table and column identifiers.
- Do not invent columns, primary keys, foreign keys, source mappings,
  constraints, or migration rules.
- Distinguish source facts from design recommendations.
- When evidence is missing, use an empty value rather than guessing.
- Keep source_format as enterprise_excel_specification.
- Produce one structured column entry for each supported source column.
- Use Traditional Chinese for semantic descriptions and recommendations
  when appropriate, while preserving physical identifiers unchanged.
"""


def create_design_document_agent(
    model,
) -> Agent:
    return Agent(
        model=model,
        output_type=DesignDocumentInterpretation,
        instructions=(
            DESIGN_DOCUMENT_AGENT_INSTRUCTIONS
        ),
    )


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
        settings["max_tokens"] = num_predict

    return settings


def interpret_enterprise_design_document(
    *,
    workbook_context: dict,
    llm_cfg: dict,
) -> dict:
    """
    Interpret an uploaded enterprise database design document.

    The application is responsible for extracting the workbook
    into workbook_context.

    This Agent converts those supplied source facts into the
    structured DesignDocumentInterpretation contract.
    """

    if (
        not llm_cfg
        or not llm_cfg.get("enabled")
    ):
        raise RuntimeError(
            "LLM backend is disabled."
        )

    model = build_agent_model(
        llm_cfg
    )

    agent = create_design_document_agent(
        model
    )

    prompt = (
        "Interpret the following enterprise database design "
        "document context. Use only supplied source facts.\n\n"
        "SOURCE DESIGN DOCUMENT:\n"
        + json.dumps(
            workbook_context,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    result = agent.run_sync(
        prompt,
        model_settings=(
            _agent_model_settings(
                llm_cfg
            )
        ),
    )

    return result.output.model_dump()


