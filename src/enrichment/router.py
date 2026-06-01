from fastapi import APIRouter, HTTPException
from src.ocr.schemas import BusinessCard 
from src.enrichment.schemas import EnrichmentResponse
from src.enrichment.service import enrich
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=EnrichmentResponse)
async def process_enrichment(request: BusinessCard):
    """
    Takes a business card extracted and returns enriched contact data (brief, keywords, highlights)
    using Gemini AI.
    """
    try:    
        result = await enrich(request)
        return result
    except Exception as e:
        logger.error(f"Enrichment error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process enrichment data")
