from pydantic import BaseModel, Field


class DatabaseDictionarySuggestion(BaseModel):
    """
    Structured semantic description of one enterprise database.

    This model represents an AI-generated suggestion only.
    Human review is required before saving it to the
    enterprise database dictionary.
    """

    source_db: str = Field(
        description=(
            "Physical PostgreSQL database name. "
            "Must match the supplied source database."
        ),
    )

    business_name: str = Field(
        description=(
            "Human-readable business name for the database."
        ),
    )

    business_domain: str = Field(
        description=(
            "Primary enterprise business domain represented "
            "by the database."
        ),
    )

    business_purpose: str = Field(
        description=(
            "Business purpose of the database."
        ),
    )

    business_scope: str = Field(
        description=(
            "Business information scope covered by the database."
        ),
    )

    business_keywords: list[str] = Field(
        default_factory=list,
        description=(
            "Concise business keywords useful for semantic "
            "database discovery."
        ),
    )

    typical_questions: list[str] = Field(
        default_factory=list,
        description=(
            "Representative business questions that could "
            "reasonably be answered using this database."
        ),
    )

    ai_description: str = Field(
        description=(
            "Conservative AI-oriented description explaining "
            "what this database represents and when it should "
            "be considered during semantic data discovery."
        ),
    )
