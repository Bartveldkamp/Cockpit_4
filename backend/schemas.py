from pydantic import BaseModel
from typing import Any, Dict, List

class ToolModel(BaseModel):
    name: str

class StepModel(BaseModel):
    tool: ToolModel
    parameters: Dict[str, Any]
    reason: str

class PlanModel(BaseModel):
    plan: List[StepModel]
