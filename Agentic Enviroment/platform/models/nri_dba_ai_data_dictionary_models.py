from typing import Literal

from pydantic import BaseModel, Field, model_validator


SemanticType = Literal[
    "identifier",
    "dimension",
    "measure",
    "measure_amount",
    "measure_count",
    "time",
    "geography",
    "geo_coordinate",
    "attribute",
    "measure_or_code",
]

DataRole = Literal[
    "",
    "primary_key",
    "foreign_key",
    "dimension",
    "measure",
    "time",
    "filter",
    "label",
    "code",
]

TableRole = Literal[
    "master",
    "dimension",
    "fact",
    "transaction",
    "event",
    "snapshot",
    "mapping",
    "reference",
    "configuration",
    "audit",
    "metadata",
    "unknown",
]


class AIDataDictionaryTableProfile(BaseModel):
    business_name: str = ""
    business_purpose: str = ""
    subject_area: str = ""
    grain_description: str = ""
    business_key: str = ""
    table_role: TableRole = "unknown"
    refresh_frequency: str = ""
    owner_department: str = ""
    ai_description: str = ""
    bi_usage: str = ""
    llm_usage: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    review_note: str = ""


class AIDataDictionaryColumn(BaseModel):
    column_name: str
    business_name: str = ""
    description: str = ""
    business_meaning: str = ""
    semantic_type: SemanticType
    data_role: DataRole = ""
    allowed_values: str = ""
    example_values: str = ""
    aggregation_hint: str = ""
    filter_hint: str = ""
    join_hint: str = ""
    quality_risk: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    review_note: str = ""
    verified: bool = False

    @model_validator(mode="after")
    def force_draft(self):
        self.verified = False
        return self


class AIDataDictionaryDesignReview(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_dictionary_items: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class AIDataDictionarySection(BaseModel):
    heading: str = ""
    type: Literal["text", "table"]
    content: str = ""
    table_id: Literal[
        "ai_table_profile",
        "ai_column_dictionary",
        "design_review",
    ] | None = None
    description: str = ""

    @model_validator(mode="after")
    def validate_section(self):
        if self.type == "text":
            self.table_id = None
            self.description = ""
        return self


class AIDataDictionaryReport(BaseModel):
    title: str = "AI 資料字典與資料表設計審查報告"
    table_profile: AIDataDictionaryTableProfile
    column_dictionary: list[AIDataDictionaryColumn]
    design_review: AIDataDictionaryDesignReview
    sections: list[AIDataDictionarySection] = Field(default_factory=list)
