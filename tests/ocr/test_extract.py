from datetime import datetime
from src.ocr.service import pipline_ocr_to_llm
import asyncio

async def test_pipline_ocr_to_llm():
    with open("src\ocr\sample\z7865925149626_e5b7e9e62ccb6c1254df42fac172b8cd.jpg", "rb") as f1, \
         open("src\ocr\sample\z7865925149626_e5b7e9e62ccb6c1254df42fac172b8cd.jpg", "rb") as f2:
        img_bytes1 = f1.read()
        img_bytes2 = f2.read()
    result = await pipline_ocr_to_llm([img_bytes1, img_bytes2])
    print("LLM Result: ", result)

if __name__ == "__main__":
    try:
        asyncio.run(test_pipline_ocr_to_llm())
    except KeyboardInterrupt:
        pass