import asyncio
from src.database import init_db
from src.ocr.service import pipline_ocr_to_llm


async def run():
    # Kết nối MongoDB Atlas (đọc MONGODB_URL từ .env)
    await init_db()

    with open(r"src\\ocr\\sample\\z7865925154338_e2586c87ac7c8bfd01f694fe913ea1eb.jpg", "rb") as f1, \
         open(r"src\\ocr\\sample\\z7865925180098_79b5db86612e434ac51e3c6a7eadf788.jpg", "rb") as f2:
        img_bytes1 = f1.read()
        img_bytes2 = f2.read()

    scan, extracted = await pipline_ocr_to_llm(
        images_data=[img_bytes1, img_bytes2],
        owner_id="6a16591fde6cb0dd33f1832f",
        processing_id="PRC-20260527-9SODVT",
    )

    print("Scan ID        :", scan.processing_id)
    print("Scan status    :", scan.status)
    print("Extracted data :", extracted)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
