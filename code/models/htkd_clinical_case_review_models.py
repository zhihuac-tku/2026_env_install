 # py code beginning

from pydantic import (
    BaseModel,
    Field,
)


class ClinicalFinding(
    BaseModel
):
    finding: str

    status: str = "present"

    onset: str | None = None

    detail: str | None = None


class MedicationMention(
    BaseModel
):
    name: str | None = None

    description: str | None = None

    time: str | None = None


class PIIStatus(
    BaseModel
):
    detected: bool = False

    removed_types: list[str] = Field(
        default_factory=list
    )


class PreparedClinicalCase(
    BaseModel
):
    age: int | None = None

    sex: str | None = None

    chief_complaint: list[str] = Field(
        default_factory=list
    )

    current_findings: list[
        ClinicalFinding
    ] = Field(
        default_factory=list
    )

    negative_findings: list[str] = Field(
        default_factory=list
    )

    medical_history: list[str] = Field(
        default_factory=list
    )

    medications: list[
        MedicationMention
    ] = Field(
        default_factory=list
    )

    allergies: list[str] = Field(
        default_factory=list
    )

    laboratory_and_vitals: list[str] = Field(
        default_factory=list
    )

    missing_information: list[str] = Field(
        default_factory=list
    )

    pii: PIIStatus = Field(
        default_factory=PIIStatus
    )

# =========================================
# CLINICAL REVIEW / REACT MODELS
# =========================================

class ClinicalReviewToolStep(
    BaseModel
):
    """
    Operational ReAct trace.

    This records tool activity only.
    It does not expose model chain-of-thought.
    """

    action: str

    query: str | None = None

    result_count: int | None = None

    note: str | None = None


class ClinicalCaseReviewResult(
    BaseModel
):
    """
    Structured output from the Clinical
    Review Agent.
    """

    review_summary: str = ""

    reviewed_case_concepts: list[str] = Field(
        default_factory=list
    )

    unresolved_questions: list[str] = Field(
        default_factory=list
    )

