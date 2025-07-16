# backend/lucidus/api.py
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List

from .verification import verify_code

logger = logging.getLogger(__name__)
router = APIRouter()

class LucidusRequest(BaseModel):
    code_snippet: str
    context: str = ""

class LucidusAnalysisResponse(BaseModel):
    complexity: str
    confidence: float
    verdict: str
    reasoning: str
    evidence: List[Dict[str, Any]]

@router.post("/lucidus_verify", response_model=LucidusAnalysisResponse)
async def lucidus_verify_endpoint(request: LucidusRequest):
    try:
        # Note: assuming verify_code returns a dict compatible with LucidusAnalysisResponse
        analysis = await verify_code(code_snippet=request.code_snippet)
        return LucidusAnalysisResponse(**analysis)
    except Exception as e:
        logger.error(f"Error during Lucidus verification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
