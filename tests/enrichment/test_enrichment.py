import asyncio
import json
from src.enrichment.service import enrich
from src.ocr.schemas import BusinessCard

async def run_test():
    # Tạo dữ liệu BusinessCard mock
    mock_card = BusinessCard(
        name="John Doe",
        phones=["+1-555-0198"],
        email="john.doe@theimprobability.co",
        company="The Improbability Co.",
        position="Software Engineer",
        address="123 Tech Lane, Silicon Valley, CA",
        website="https://theimprobability.co/"
    )
    
    print("Bắt đầu chạy AI Enrichment...")
    try:
        res = await enrich(mock_card)
        print("\n=== KẾT QUẢ ENRICHMENT ===")
        print(f"Status: {res.generation_status}")
        print(f"Brief: {res.professional_brief}")
        print(f"Keywords: {res.keywords}")
        print(f"Highlights: {res.highlights}")
        print("==========================")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")

if __name__ == '__main__':
    asyncio.run(run_test())