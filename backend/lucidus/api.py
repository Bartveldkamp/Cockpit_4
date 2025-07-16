# backend/lucidus/api.py
import logging
from fastapi import APIRouter, HTTPException
from typing import Dict

from .verification import verify_code
from .schemas import LucidusRequest, LucidusAnalysisResponse

# Add these two lines
logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/lucidus_verify", response_model=LucidusAnalysisResponse)
async def lucidus_verify_endpoint(code_data: LucidusRequest):
    try:
        analysis = await verify_code(code_data.code_snippet)
        return LucidusAnalysisResponse(**analysis)
    except Exception as e:
        logger.error(f"Error during Lucidus verification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
