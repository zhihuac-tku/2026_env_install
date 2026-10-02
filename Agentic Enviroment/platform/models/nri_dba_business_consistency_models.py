from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BusinessConsistencySection(BaseModel):
    heading: str = ""
    type: Literal["text", "table"]
    content: str = ""
    table_id: Literal["column_usage"] | None = None
    description: str = ""

    @model_validator(mode="after")
    def validate_block(self):
        if self.type == "table":
            if self.table_id != "column_usage":
                raise ValueError(
                    "Business Consistency table blocks must use "
                    "table_id='column_usage'."
                )
            self.content = ""
        else:
            self.table_id = None
            self.description = ""
        return self


class BusinessConsistencyReport(BaseModel):
    title: str = "PostgreSQL 欄位業務一致性審查報告"
    sections: list[BusinessConsistencySection] = Field(default_factory=list)
