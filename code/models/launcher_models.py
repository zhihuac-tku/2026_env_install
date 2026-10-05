from typing import Literal
from pydantic import BaseModel, Field

class LauncherClassification(BaseModel):
    app_name: str
    category: Literal["Applications","Knowledge & Data","AI & Agents","Security & Access","Operations"]
    app_type: str
    description: str
    tags: list[str]
    visibility: Literal["user","dba","admin","restricted"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
