ffrom fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from .verification import verify_code

router = APIRouter()

class LucidusAnalysisResponse(BaseModel):
    complexity: str
    confidence: float
    verdict: str
    reasoning: str
    evidence: List[Dict[str, Any]]

@router.post("/lucidus_verify", response_model=LucidusAnalysisResponse)
async def lucidus_verify_endpoint(code_data: Dict[str, str]):
    code_snippet = code_data.get("code_snippet")
    context = code_data.get("context", "")

    if not code_snippet:
        raise HTTPException(status_code=400, detail="'code_snippet' is required for Lucidus verification.")

    try:
        analysis_result = await verify_code(code_snippet=code_snippet, context=context)
        return LucidusAnalysisResponse(**analysis_result)
    except Exception as e:
        logger.error(f"Error during Lucidus verification: {e}")
        raise HTTPException(status_code=500, detail=f"Error during Lucidus verification: {e}")
