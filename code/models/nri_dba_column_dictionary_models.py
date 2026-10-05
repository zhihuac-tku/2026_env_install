from typing import Literal

from pydantic import BaseModel, Field


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
    "primary_key",
    "foreign_key",
    "dimension",
    "measure",
    "time",
    "filter",
    "label",
    "code",
    "",
]


class ColumnDictionarySuggestion(BaseModel):
    """
    Typed AI suggestion for one physical PostgreSQL column.
    """

    column_name: str

    business_name: str = ""
    description: str = ""

    semantic_type: SemanticType = "attribute"
    data_role: DataRole = ""

    allowed_values: str = ""
    example_values: str = ""

    aggregation_hint: str = ""
    filter_hint: str = ""
    join_hint: str = ""


class ColumnDictionarySuggestionSet(BaseModel):
    """
    Structured output containing suggestions for the supplied
    physical columns.
    """

    columns: list[ColumnDictionarySuggestion] = Field(
        default_factory=list,
    )
