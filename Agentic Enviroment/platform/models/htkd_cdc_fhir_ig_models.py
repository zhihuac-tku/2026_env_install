 # py code beginning

"""Pydantic models for CDC reporting requirements.

These models describe requirements extracted from an
authoritative CDC reporting document.

FHIR mapping is intentionally NOT included here.
FHIR representation is handled in a later stage.
"""

from pydantic import BaseModel, Field


# =========================================
# REPORT FIELD COMPONENT
# =========================================

class CDCReportFieldComponent(BaseModel):
    """One component inside a composite report field."""

    name: str = Field(
        description=(
            "Component name supported by the "
            "source reporting document."
        )
    )

    data_type: str | None = Field(
        default=None,
        description=(
            "Logical source data type such as "
            "text, date, boolean, choice, "
            "identifier, address, or phone."
        ),
    )

    options: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit selectable options appearing "
            "for this component in the source "
            "document."
        ),
    )

    condition: str | None = Field(
        default=None,
        description=(
            "Condition under which this component "
            "applies when explicitly supported "
            "by the source document."
        ),
    )


# =========================================
# REPORT FIELD
# =========================================

class CDCReportField(BaseModel):
    """One reporting field found in a CDC report."""

    section: str = Field(
        description=(
            "Section of the CDC report containing "
            "this field."
        )
    )

    field_name: str = Field(
        description=(
            "Field name as represented in the "
            "source reporting document."
        )
    )

    description: str | None = Field(
        default=None,
        description=(
            "Additional description or instruction "
            "associated with the field."
        ),
    )

    data_type: str | None = Field(
        default=None,
        description=(
            "Observed or inferred logical source "
            "data type such as text, date, boolean, "
            "choice, identifier, address, phone, "
            "or composite."
        ),
    )

    required: bool | None = Field(
        default=None,
        description=(
            "Whether the source document explicitly "
            "indicates that the field is required. "
            "Use None when this cannot be determined."
        ),
    )

    options: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit selectable options appearing "
            "in the source document for a simple "
            "choice field."
        ),
    )

    components: list[
        CDCReportFieldComponent
    ] = Field(
        default_factory=list,
        description=(
            "Individual logical components of a "
            "composite report field. Leave empty "
            "for simple fields."
        ),
    )

    source_text: str | None = Field(
        default=None,
        description=(
            "Relevant source text supporting the "
            "extracted field."
        ),
    )


# =========================================
# REPORT SECTION
# =========================================

class CDCReportSection(BaseModel):
    """A logical section of a CDC report."""

    section_name: str = Field(
        description=(
            "Section name appearing in or derived "
            "from the reporting document."
        )
    )

    description: str | None = Field(
        default=None,
        description=(
            "Section-level instructions or "
            "description."
        ),
    )

    fields: list[
        CDCReportField
    ] = Field(
        default_factory=list,
        description=(
            "Reporting fields belonging to this "
            "section."
        ),
    )


# =========================================
# REPORT REQUIREMENT
# =========================================

class CDCReportRequirement(BaseModel):
    """Structured representation of one CDC report."""

    report_name: str = Field(
        description=(
            "Name or title of the CDC reporting "
            "document."
        )
    )

    report_version: str | None = Field(
        default=None,
        description=(
            "Version, revision date, or effective "
            "version found in the source document."
        ),
    )

    source_filename: str | None = Field(
        default=None,
        description=(
            "Original uploaded source filename."
        ),
    )

    report_description: str | None = Field(
        default=None,
        description=(
            "Short description of the report "
            "purpose when supported by the source."
        ),
    )

    sections: list[
        CDCReportSection
    ] = Field(
        default_factory=list,
        description=(
            "Logical reporting sections extracted "
            "from the source document."
        ),
    )

    report_instructions: list[str] = Field(
        default_factory=list,
        description=(
            "Report-level instructions explicitly "
            "present in the source document."
        ),
    )

    extraction_notes: list[str] = Field(
        default_factory=list,
        description=(
            "Important uncertainties or limitations "
            "encountered during extraction."
        ),
    )

# =========================================
# FHIR ELEMENT EVIDENCE
# =========================================

class CDCFHIRElementEvidence(BaseModel):
    """One FHIR element supported by retrieved evidence."""

    package_name: str = Field(
        description=(
            "FHIR package providing this evidence, "
            "such as hl7.fhir.r4.core."
        )
    )

    package_version: str | None = Field(
        default=None,
        description=(
            "Version of the FHIR package providing "
            "the evidence."
        ),
    )

    artifact_id: str = Field(
        description=(
            "FHIR StructureDefinition artifact ID."
        )
    )

    artifact_url: str | None = Field(
        default=None,
        description=(
            "Canonical URL of the FHIR "
            "StructureDefinition."
        ),
    )

    element_path: str = Field(
        description=(
            "Exact FHIR element path supported by "
            "the retrieved evidence."
        )
    )

    min_cardinality: int | None = Field(
        default=None,
        description=(
            "Minimum cardinality defined by the "
            "retrieved FHIR artifact."
        ),
    )

    max_cardinality: str | None = Field(
        default=None,
        description=(
            "Maximum cardinality defined by the "
            "retrieved FHIR artifact."
        ),
    )

    type_codes: list[str] = Field(
        default_factory=list,
        description=(
            "FHIR datatype codes allowed for this "
            "element."
        ),
    )

    target_profiles: list[str] = Field(
        default_factory=list,
        description=(
            "FHIR target profiles associated with "
            "Reference or canonical types."
        ),
    )

    binding_strength: str | None = Field(
        default=None,
        description=(
            "FHIR terminology binding strength "
            "when present."
        ),
    )

    binding_value_set: str | None = Field(
        default=None,
        description=(
            "Canonical ValueSet URL bound to this "
            "FHIR element when present."
        ),
    )

    short_description: str | None = Field(
        default=None,
        description=(
            "Short description from the FHIR "
            "element definition."
        ),
    )


# =========================================
# FHIR TERMINOLOGY EVIDENCE
# =========================================

class CDCFHIRTerminologyEvidence(BaseModel):
    """Terminology evidence discovered during mapping."""

    value_set_url: str | None = Field(
        default=None,
        description=(
            "Canonical FHIR ValueSet URL relevant "
            "to the mapped element."
        ),
    )

    binding_strength: str | None = Field(
        default=None,
        description=(
            "FHIR terminology binding strength."
        ),
    )

    code_system_urls: list[str] = Field(
        default_factory=list,
        description=(
            "CodeSystem canonical URLs referenced "
            "by the ValueSet."
        ),
    )

    evidence_note: str | None = Field(
        default=None,
        description=(
            "Short factual note about terminology "
            "evidence retrieved from HTKD."
        ),
    )


# =========================================
# ONE CDC REQUIREMENT → FHIR MAPPING
# =========================================

class CDCFHIRRequirementMapping(BaseModel):
    """FHIR mapping analysis for one CDC requirement."""

    section: str = Field(
        description=(
            "Original CDC report section."
        )
    )

    field_name: str = Field(
        description=(
            "Original CDC report field name."
        )
    )

    component_name: str | None = Field(
        default=None,
        description=(
            "Original component name when the CDC "
            "field is composite. None for a simple "
            "field."
        ),
    )

    source_data_type: str | None = Field(
        default=None,
        description=(
            "Logical source datatype from the "
            "confirmed CDC requirement."
        ),
    )

    mapping_status: str = Field(
        description=(
            "Evidence-based mapping status. "
            "Allowed values are Covered, Partial, "
            "Missing, or Needs Investigation."
        )
    )

    fhir_resource: str | None = Field(
        default=None,
        description=(
            "Primary FHIR resource identified by "
            "the mapping analysis, such as Patient "
            "or Condition."
        ),
    )

    fhir_elements: list[
        CDCFHIRElementEvidence
    ] = Field(
        default_factory=list,
        description=(
            "One or more FHIR elements supported "
            "by retrieved evidence."
        ),
    )

    terminology: list[
        CDCFHIRTerminologyEvidence
    ] = Field(
        default_factory=list,
        description=(
            "Terminology evidence relevant to this "
            "mapping."
        ),
    )

    mapping_explanation: str = Field(
        description=(
            "Concise explanation of how the CDC "
            "requirement can or cannot currently "
            "be represented by the inspected FHIR "
            "artifacts."
        )
    )

    unresolved_questions: list[str] = Field(
        default_factory=list,
        description=(
            "Questions that could not be resolved "
            "from currently available FHIR evidence."
        ),
    )


# =========================================
# PAGE 4 FHIR MAPPING RESULT
# =========================================

class CDCFHIRMappingResult(BaseModel):
    """Structured output of the Page 4 mapping agent."""

    report_name: str = Field(
        description=(
            "CDC report being analyzed."
        )
    )

    report_version: str | None = Field(
        default=None,
        description=(
            "CDC report version or revision."
        ),
    )

    mappings: list[
        CDCFHIRRequirementMapping
    ] = Field(
        default_factory=list,
        description=(
            "FHIR mapping results for the confirmed "
            "CDC reporting requirements."
        ),
    )

    packages_consulted: list[str] = Field(
        default_factory=list,
        description=(
            "FHIR packages actually consulted "
            "during the mapping analysis."
        ),
    )

    analysis_notes: list[str] = Field(
        default_factory=list,
        description=(
            "Important evidence limitations or "
            "analysis notes."
        ),
    )

