"""
Preprocess adapter for the OCR pipeline API.

Bridges the GCS download layer (``list[bytes]``) with the in-memory
preprocessing core (``preprocess_pipeline_in_memory``), which returns a
``np.ndarray``.  This wrapper re-encodes each processed array back to bytes
so the output is a ``list[bytes]`` ready for the OCR module.

The core function ``preprocess_pipeline_in_memory`` is **not modified**.
"""

from __future__ import annotations

import logging

import cv2

from .config import preprocess_settings
from .service import preprocess_pipeline_in_memory

logger = logging.getLogger(__name__)


async def preprocess_image_bytes(
    images_raw: list[bytes],
    *,
    output_format: str = preprocess_settings.OUTPUT_FORMAT,
) -> list[bytes]:
    """Run the preprocessing pipeline on a list of raw image byte strings.

    For each raw ``bytes`` object:
      1. Run the full in-memory preprocessing pipeline
         (DPI normalisation, orientation fix, CLAHE, format conversion).
      2. Re-encode the resulting ``np.ndarray`` back to bytes in *output_format*.

    Parameters
    ----------
    images_raw:
        Raw image bytes — typically downloaded directly from GCS.
    output_format:
        Target image format for encoding (default: ``preprocess_settings.OUTPUT_FORMAT``).

    Returns
    -------
    list[bytes]
        One preprocessed bytes object per input image, in the same order.
    """
    ext_map = {
        "png": ".png",
        "jpeg": ".jpg",
        "jpg": ".jpg",
        "webp": ".webp",
        "tiff": ".tiff",
    }
    fmt = output_format.lower().strip(".")
    ext = ext_map.get(fmt, ".png")

    images_data: list[bytes] = []

    for idx, raw_bytes in enumerate(images_raw):
        # Run the full preprocessing pipeline in-memory (no DB, no disk)
        img_array, metadata = await preprocess_pipeline_in_memory(
            raw_bytes,
            output_format=output_format,
        )

        # Re-encode the processed np.ndarray → bytes
        success, buffer = cv2.imencode(ext, img_array)
        if not success:
            logger.error(
                "cv2.imencode failed for image index %d (format=%s)",
                idx,
                output_format,
            )
            raise RuntimeError(
                f"Failed to encode preprocessed image at index {idx}"
            )

        image_bytes: bytes = buffer.tobytes()
        logger.info(
            "Preprocessed image[%d] → %d bytes (steps=%s)",
            idx,
            len(image_bytes),
            metadata.get("steps_applied"),
        )
        images_data.append(image_bytes)

    return images_data
