 # py code beginning

from pydantic_ai import Agent

from nri_ai_core.ai_runtime import (
    build_agent_model,
)

from models.htkd_clinical_case_review_models import (
    PreparedClinicalCase,
)


def create_htkd_clinical_case_preparation_agent(
    llm_cfg: dict,
):

    model = build_agent_model(
        llm_cfg
    )

    return Agent(
        model=model,
        output_type=PreparedClinicalCase,
    )

