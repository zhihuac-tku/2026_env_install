"""Typed final-output contract for the NRI DBA Investigator.

Pass 14.1 deliberately keeps runtime/tool telemetry out of the model-generated
answer. Pydantic AI owns tool execution; the model owns DBA conclusions.
"""

from typing import Literal

from pydantic import BaseModel, Field


class DBAInvestigationFinding(BaseModel):
    category: Literal[
        "table_design",
        "primary_key",
        "foreign_key",
        "index",
        "constraint",
        "dictionary",
        "relationship",
        "naming",
        "data_type",
        "other",
    ] = "other"

    severity: Literal[
        "INFO",
        "LOW",
        "MEDIUM",
        "HIGH",
    ] = "INFO"

    finding: str
    evidence: list[str] = Field(default_factory=list)
    recommendation: str = ""
    requires_human_review: bool = True


class DBAInvestigationResult(BaseModel):
    summary: str
    findings: list[DBAInvestigationFinding] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
