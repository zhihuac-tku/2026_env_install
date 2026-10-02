from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
ColumnReviewStatus = Literal["GOOD", "REVIEW", "CHANGE"]
ConstraintType = Literal[
    "CHECK",
    "UNIQUE",
    "FK",
    "NOT_NULL",
    "INDEX",
    "OTHER",
]
ControlColumnDecision = Literal[
    "ADD",
    "OPTIONAL",
    "DO_NOT_ADD",
]


class DBAColumnReview(BaseModel):
    column_name: str = ""
    status: ColumnReviewStatus = "REVIEW"
    issue: str = ""
    recommendation: str = ""


class DBAConstraintRecommendation(BaseModel):
    type: ConstraintType = "OTHER"
    columns: list[str] = Field(default_factory=list)
    recommendation: str = ""
    reason: str = ""


class DBAControlColumnRecommendation(BaseModel):
    column_name: str = ""
    decision: ControlColumnDecision = "OPTIONAL"
    reason: str = ""


class DBADesignReview(BaseModel):
    executive_summary: str = ""
    overall_assessment: str = ""
    final_recommendation: str = ""
    risk_level: RiskLevel = "MEDIUM"

    table_purpose_review: str = ""
    grain_review: str = ""
    primary_key_review: str = ""
    foreign_key_review: str = ""

    column_reviews: list[DBAColumnReview] = Field(default_factory=list)
    constraint_recommendations: list[DBAConstraintRecommendation] = Field(
        default_factory=list,
    )
    control_column_recommendations: list[
        DBAControlColumnRecommendation
    ] = Field(default_factory=list)

    naming_findings: list[str] = Field(default_factory=list)
    normalization_findings: list[str] = Field(default_factory=list)
    priority_actions: list[str] = Field(default_factory=list)
