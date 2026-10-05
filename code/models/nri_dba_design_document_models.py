from pydantic import BaseModel, Field


class DesignDocumentColumn(BaseModel):
    column_seq: int = 0
    column_name: str = ""
    source_data_type: str = ""
    recommended_postgresql_type: str = ""
    is_nullable: str = ""
    column_default: str = ""
    comment: str = ""
    business_description: str = ""
    source_table: str = ""
    source_column: str = ""
    migration_rule: str = ""
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_target_table: str = ""
    foreign_key_target_column: str = ""
    design_recommendation: str = ""


class DesignDocumentForeignKey(BaseModel):
    source_columns: list[str] = Field(default_factory=list)
    target_table: str = ""
    target_columns: list[str] = Field(default_factory=list)
    constraint_name_raw: str = ""


class DesignDocumentInterpretation(BaseModel):
    database_name: str = ""
    schema_name: str = ""
    table_name: str = ""
    table_description: str = ""
    source_format: str = "enterprise_excel_specification"

    columns: list[DesignDocumentColumn] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[DesignDocumentForeignKey] = Field(default_factory=list)

    document_warnings: list[str] = Field(default_factory=list)
    table_level_recommendations: list[str] = Field(default_factory=list)
