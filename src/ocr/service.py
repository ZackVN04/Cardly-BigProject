# TODO(P4 — Cường Ngô + Thanh Thiệt): Implement OCR + AI Vision service
# Functions to implement:
#   run_ocr(processing_id: str, image_path: str) -> OcrResult
#   run_vision(processing_id: str, image_path: str) -> AiVisionResult
#   Both called via asyncio.gather() in pipeline/stages.py
#
# Output contract (MUST match mock_data/*_ocr_output.json):
#   ocr.raw_text: str
#   ocr.blocks: [{text, bbox:[x,y,w,h], confidence}]
#   vision.doc_type: "passport_au" | "medicare" | "driver_licence_vic" | "unknown"
#   vision.detected_regions: [{label, bbox, confidence}]
#   confidence: float 0.0–1.0 (NOT percent)
