 # py code beginning

"""CDC Report Requirement Agent.

Purpose:
- Read an already extracted CDC reporting document.
- Identify the reporting structure and requirements.
- Return a structured CDCReportRequirement.

This agent does NOT:
- perform FHIR mapping,
- perform IG comparison,
- perform gap analysis,
- design profiles or extensions,
- generate FSH.
"""

from __future__ import annotations

import json

from pydantic_ai import Agent

from models.htkd_cdc_fhir_ig_models import (
    CDCReportRequirement,
)

from htkd.fhir_ig.document.report_reader import (
    ExtractedReportDocument,
)

from nri_ai_core.ai_runtime import (
    build_agent_model,
)


# =========================================
# SYSTEM INSTRUCTIONS
# =========================================

CDC_REPORT_REQUIREMENT_INSTRUCTIONS = """
You are a CDC healthcare reporting requirement
analysis agent.

Your job is to analyze an extracted CDC reporting
document and produce a structured representation
of what the source document requires.

You are NOT designing FHIR at this stage.

Follow these rules carefully:

1. Use only information supported by the supplied
   source document.

2. Preserve the source document's reporting
   structure whenever possible.

3. Identify logical report sections and the
   reporting fields belonging to each section.

4. Preserve field names from the source document
   as closely as possible.

5. Extract explicit selectable options when they
   appear in the source document.

6. Determine a logical source data type only when
   it can reasonably be inferred from the source.

   Examples include:
   - text
   - date
   - boolean
   - choice
   - identifier
   - address
   - phone
   - composite

7. For a simple field, use one logical data type
   and leave components empty.

   Example:

   性別
   data_type = "choice"
   options = ["男", "女", "第三性別"]
   components = []

8. When one report field contains multiple logical
   data components, represent it as a composite
   field.

   For a composite field:
   - set data_type to "composite"
   - use components for the individual parts
   - preserve each component's logical data type
   - preserve component options when present
   - preserve a condition only when supported
     by the source document

9. Do not use combined data type strings such as:

   - "choice/date"
   - "choice/text"
   - "choice/text/date"

   Use data_type = "composite" and represent the
   individual parts in components instead.

10. Do not invent components that are not
    supported by the source document.

    For example, do not invent start_date,
    end_date, location, or other subfields merely
    because they are commonly associated with a
    concept.

11. Keep selectable options at the level where
    they actually belong.

    For a simple choice field, place them in the
    field's options.

    For a composite field, place options in the
    appropriate component whenever possible.

12. Do not assume that a field is required merely
    because it appears on the form.

13. Set required to null when required status
    cannot be determined from the source.

14. Preserve relevant source text as evidence for
    each extracted field when available.

15. Extract report-level instructions separately
    from reporting fields.

16. Record uncertainties, ambiguous structures,
    extraction limitations, or missing information
    in extraction_notes.

17. Do not invent missing reporting requirements.

18. Do not add FHIR resources, FHIR elements,
    profiles, extensions, ValueSets, CodeSystems,
    mappings, or implementation recommendations.

19. Do not convert Chinese report fields or disease
    names into ICD, SNOMED CT, LOINC, or other
    terminology codes at this stage.

20. Preserve Chinese source terminology and field
    names as closely as possible.

21. Do not perform clinical interpretation.

22. Return only the structured
    CDCReportRequirement output requested by the
    output model.
"""


# =========================================
# CREATE AGENT
# =========================================


def create_htkd_cdc_report_requirement_agent(
    llm_cfg: dict,
) -> Agent:
    """Create the CDC report requirement agent."""

    model = build_agent_model(
        llm_cfg
    )

    return Agent(
        model=model,
        output_type=CDCReportRequirement,
        instructions=(
            CDC_REPORT_REQUIREMENT_INSTRUCTIONS
        ),
    )


# =========================================
# PREPARE AGENT INPUT
# =========================================


def build_cdc_report_requirement_prompt(
    *,
    report_document: ExtractedReportDocument,
) -> str:
    """Build grounded input for the agent."""

    payload = {
        "source_document": {
            "file_name":
                report_document.file_name,

            "file_type":
                report_document.file_type,

            "paragraphs":
                report_document.paragraphs,

            "tables": [
                table.model_dump()
                for table
                in report_document.tables
            ],

            "sheets": [
                sheet.model_dump()
                for sheet
                in report_document.sheets
            ],

            "extraction_notes":
                report_document.extraction_notes,

            "extracted_text":
                report_document.text,
        }
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


# =========================================
# RUN REQUIREMENT EXTRACTION
# =========================================


def extract_cdc_report_requirements(
    *,
    report_document: ExtractedReportDocument,
    llm_cfg: dict,
) -> CDCReportRequirement:
    """Extract structured CDC report requirements."""

    agent = (
        create_htkd_cdc_report_requirement_agent(
            llm_cfg
        )
    )

    prompt = (
        build_cdc_report_requirement_prompt(
            report_document=report_document,
        )
    )

    result = agent.run_sync(
        prompt
    )

    requirement = result.output

    # Preserve original filename even if the
    # model omitted or changed it.
    requirement.source_filename = (
        report_document.file_name
    )

    # Preserve reader-level extraction notes.
    for note in (
        report_document.extraction_notes
    ):

        if (
            note
            and note
            not in requirement.extraction_notes
        ):
            requirement.extraction_notes.append(
                note
            )

    return requirement

