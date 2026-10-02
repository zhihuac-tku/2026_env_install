from typing import Literal

from pydantic import BaseModel, Field


RefreshFrequency = Literal[
    "",
    "Ad hoc",
    "Daily",
    "Weekly",
    "Monthly",
    "Quarterly",
    "Yearly",
    "Unknown",
]


class TableDictionarySuggestion(BaseModel):
    """
    Typed AI suggestion for one table-level NRI data dictionary entry.

    Physical identifiers are controlled by the application and are
    not part of the model-generated semantic contract.
    """

    business_name: str = ""
    business_purpose: str = ""
    subject_area: str = ""
    grain_description: str = ""
    business_key: str = ""

    refresh_frequency: RefreshFrequency = "Unknown"

    owner_department: str = ""

    ai_description: str = ""

    verified: bool = Field(
        default=False,
        description=(
            "AI suggestions are not human-verified by default."
        ),
    )
