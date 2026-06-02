import asyncio
import logging
import re
import html
from pydantic import ValidationError
from src.enrichment.schemas import EnrichmentResultBase, EnrichmentResponse
from src.ocr.schemas import BusinessCard
from google import genai
from google.genai.types import Tool, GenerateContentConfig, UrlContext, GoogleSearch
from .clients.gemini_client import get_gemini_client
from .constants import GenerationStatus

logger = logging.getLogger(__name__)

def sanitize_text(text: str | None) -> str | None:
    """Sanitize generated AI content by removing HTML tags and unescaping entities."""
    if not text:
        return text
    clean = re.sub(r'<[^>]+>', '', text)
    return html.unescape(clean).strip()

async def enrich(business_card: BusinessCard) -> EnrichmentResponse:
    logger.info(f"Starting AI enrichment for {business_card.name} / {business_card.company}")
    client = get_gemini_client()

    try:
        prompt = f"""
        You are a strict information enrichment engine.

        You will receive:
        1. A business card extracted from OCR
        2. A list of URLs related to that business card

        Use the business card as primary context to understand the person/company.
        Use the URLs only to enrich and verify factual information.
        Do NOT invent facts.
        Do NOT use external knowledge.
        Do NOT infer missing information.

        Business card data:
        - name: {business_card.name}
        - phones: {business_card.phones}
        - email: {business_card.email}
        - company: {business_card.company}
        - position: {business_card.position}
        - address: {business_card.address}

        URLs to analyze:
        {business_card.website}, {business_card.social_profiles}

        Return ONLY these fields:
        1. professional_brief
        - A concise summary based on the business card and supported by the URLs
        - 2–4 sentences max
        - Prefer facts from the business card first, then enrich with URL-confirmed details

        2. keywords
        - Concise professional keywords/tags
        - Include terms supported by either the business card or the URLs
        - MUST sort the keywords by relevance score (most relevant first)

        3. highlights
        - Notable factual highlights about the person/company
        - Prioritize concrete facts from the business card and confirm/extend with URLs when possible

        STRICT RULES:
        - Do not hallucinate or invent facts
        - Do not guess missing details
        - Ignore low confidence or uncertain information (S4)
        - If a field is unsupported, omit it
        - If no reliable enrichment exists, return empty arrays or empty strings
        - Every extracted item must be traceable to the provided business card data or URLs
        """

        url_context_tool = Tool(url_context=UrlContext())

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-3.1-flash-lite",
                    contents=[prompt],
                    config=GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=EnrichmentResultBase.model_json_schema(),
                        temperature=0,
                        tools=[url_context_tool],
                    )
                ),
                timeout=50.0
            )
        except asyncio.TimeoutError:
            logger.warning("AI enrichment timeout (S6) - returning TIMEOUT status")
            return EnrichmentResponse(
                generation_status=GenerationStatus.TIMEOUT
            )

        try:
            result = EnrichmentResultBase.model_validate_json(response.text)
        except ValidationError as e:
            logger.error(f"Invalid AI response format: {e}")
            return EnrichmentResponse(
                generation_status=GenerationStatus.FAILED
            )

        # BE-AI-10: Sanitization
        if result.professional_brief:
            result.professional_brief = sanitize_text(result.professional_brief)
            
        if result.highlights:
            result.highlights = [sanitize_text(h) for h in result.highlights if h]

        # S3: Deduplicate + sort keyword (preserve relevance order)
        if result.keywords:
            result.keywords = [sanitize_text(k) for k in list(dict.fromkeys(result.keywords)) if k]

        has_brief = bool(result.professional_brief and result.professional_brief.strip())
        has_keywords = bool(result.keywords)
        has_highlights = bool(result.highlights)

        if has_brief and has_keywords and has_highlights:
            status = GenerationStatus.SUCCESS
        elif not has_brief and not has_keywords and not has_highlights:
            status = GenerationStatus.FAILED
        else:
            status = GenerationStatus.PARTIAL

        # Save data to MongoDB
        
        logger.info(f"AI enrichment completed with status: {status}")
        return EnrichmentResponse(
            generation_status=status,
            professional_brief=result.professional_brief,
            keywords=result.keywords,
            highlights=result.highlights,
        )
        
    except Exception as e:
        print(f"Error calling API: {e}")
        raise