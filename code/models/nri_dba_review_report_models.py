from pydantic import BaseModel, Field


class DBAReviewReportSection(BaseModel):
    heading: str = ""
    content: str = ""
    bullets: list[str] = Field(default_factory=list)


class DBAReviewReport(BaseModel):
    title: str = "NRI Enterprise DBA Design Review"
    subtitle: str = ""
    summary: str = ""
    sections: list[DBAReviewReportSection] = Field(default_factory=list)
