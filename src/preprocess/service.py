"""
Preprocessing service layer.

Exposes the four main pipeline steps described in models.PreprocessedImage:
    • normalize_dpi      — resample to target DPI if below minimum
    • fix_orientation    — auto-detect + correct coarse rotation and fine skew
    • adjust_brightness_contrast — auto-contrast via CLAHE
    • convert_format     — encode to target format (PNG, JPEG, WEBP …)
    • preprocess_pipeline — async orchestrator that runs all steps and persists
                            a PreprocessedImage document.

Each step function is intentionally stateless: it accepts a numpy image array
(and optional metadata) and returns a transformed image plus any metadata
needed to populate PreprocessedImage fields.
"""

from __future__ import annotations

import logging
import os
import uuid

import cv2
import numpy as np
from beanie import PydanticObjectId

from .config import preprocess_settings
from .exceptions import ImageDistorted, MemoryOverflow, PreprocessFailed
from .models import PreprocessedImage, PreprocessingStatus
from .utils import detect_and_correct_orientation

logger = logging.getLogger(__name__)

PROCESSED_DIR = "storage/processed"


# ---------------------------------------------------------------------------
# Async pipeline orchestrator
# ---------------------------------------------------------------------------

async def preprocess_pipeline(
    source_path: str,
    source_image_id: PydanticObjectId,
    *,
    manual_rotation: int | None = None,
    source_dpi: int = 96,
    output_format: str = preprocess_settings.OUTPUT_FORMAT,
) -> PreprocessedImage:
    """
    Run the full preprocessing pipeline on a source image file.

    Steps executed in order:
      1. ``normalize_dpi``            — upsample to MIN_DPI if needed.
      2. ``fix_orientation``          — auto-correct rotation/skew
                                       (or apply *manual_rotation* if supplied).
      3. ``adjust_brightness_contrast`` — CLAHE contrast enhancement.
      4. ``convert_format``           — encode to *output_format*.

    The result is saved to ``storage/processed/`` and a
    :class:`~src.preprocess.models.PreprocessedImage` document is inserted
    into MongoDB (if available) and returned.

    Parameters
    ----------
    source_path:
        Filesystem path to the uploaded source image.
    source_image_id:
        MongoDB ObjectId of the original image document.
    manual_rotation:
        When not *None* (0 / 90 / 180 / 270), skip auto-detection and apply
        this exact coarse rotation.
    source_dpi:
        DPI metadata of the source scan (default 96 for web uploads).
    output_format:
        Target format string, e.g. ``"png"`` or ``"jpeg"``.

    Returns
    -------
    PreprocessedImage
        The saved preprocessing artifact document.
    """
    processing_id = str(uuid.uuid4())
    steps_applied: list[str] = []

    record = PreprocessedImage(
        processing_id=processing_id,
        source_image_id=source_image_id,
        processed_storage_path="",
        resolution_dpi=source_dpi,
        output_format=output_format,
        preprocessing_status=PreprocessingStatus.IN_PROGRESS,
    )

    try:
        # --- Load image ---
        img = cv2.imread(source_path, cv2.IMREAD_COLOR)
        if img is None:
            raise PreprocessFailed(message=f"Cannot read image: {source_path}")

        # --- Step 1: Normalize DPI ---
        img, effective_dpi = normalize_dpi(img, source_dpi)
        record.resolution_dpi = effective_dpi
        steps_applied.append(f"normalize_dpi:{effective_dpi}dpi")

        # --- Step 2: Fix orientation ---
        if manual_rotation is not None and manual_rotation in (0, 90, 180, 270):
            from .utils import rotate_fixed
            img = rotate_fixed(img, manual_rotation)
            rotation_applied = manual_rotation
            steps_applied.append(f"manual_rotation:{manual_rotation}deg")
        else:
            img, rotation_applied = fix_orientation(img)
            steps_applied.append(f"fix_orientation:{rotation_applied}deg")
        record.rotation_applied = rotation_applied

        # --- Step 3: Brightness / contrast ---
        img, brightness_delta, contrast_delta = adjust_brightness_contrast(img)
        record.brightness_delta = brightness_delta
        record.contrast_delta = contrast_delta
        steps_applied.append(
            f"clahe:brightness_delta={brightness_delta:.4f},contrast_delta={contrast_delta:.4f}"
        )

        # --- Step 4: Convert format ---
        img = convert_format(img, output_format)
        steps_applied.append(f"convert_format:{output_format}")

        # --- Save processed file ---
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        ext = output_format.lower().strip(".")
        out_filename = f"{processing_id}.{ext}"
        out_path = os.path.join(PROCESSED_DIR, out_filename)
        cv2.imwrite(out_path, img)

        record.processed_storage_path = out_path
        record.steps_applied = steps_applied
        record.preprocessing_status = PreprocessingStatus.SUCCESS

        logger.info("Pipeline SUCCESS  processing_id=%s  steps=%s", processing_id, steps_applied)

    except (PreprocessFailed, ImageDistorted, MemoryOverflow) as exc:
        record.preprocessing_status = PreprocessingStatus.FAILED
        record.error_message = str(exc)
        record.steps_applied = steps_applied
        logger.error("Pipeline FAILED  processing_id=%s  error=%s", processing_id, exc)
        raise

    except Exception as exc:  # noqa: BLE001
        record.preprocessing_status = PreprocessingStatus.FAILED
        record.error_message = str(exc)
        record.steps_applied = steps_applied
        logger.exception("Pipeline unexpected error  processing_id=%s", processing_id)
        raise PreprocessFailed(message=str(exc)) from exc

    finally:
        # Persist record regardless of success/failure (best-effort)
        try:
            await record.insert()
        except Exception as db_exc:  # noqa: BLE001
            logger.warning("Could not persist PreprocessedImage to DB: %s", db_exc)

    return record


async def preprocess_pipeline_in_memory(
    file_bytes: bytes,
    *,
    manual_rotation: int | None = None,
    source_dpi: int = 96,
    output_format: str = preprocess_settings.OUTPUT_FORMAT,
) -> tuple[np.ndarray, dict]:
    """
    Run the full preprocessing pipeline in-memory on bytes.
    Does not save to disk, does not insert to MongoDB.
    """
    steps_applied: list[str] = []

    try:
        # --- Load image from bytes ---
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise PreprocessFailed(message="Cannot decode uploaded image bytes")

        # --- Step 1: Normalize DPI ---
        img, effective_dpi = normalize_dpi(img, source_dpi)
        steps_applied.append(f"normalize_dpi:{effective_dpi}dpi")

        # --- Step 2: Fix orientation ---
        if manual_rotation is not None and manual_rotation in (0, 90, 180, 270):
            from .utils import rotate_fixed
            img = rotate_fixed(img, manual_rotation)
            rotation_applied = manual_rotation
            steps_applied.append(f"manual_rotation:{manual_rotation}deg")
        else:
            img, rotation_applied = fix_orientation(img)
            steps_applied.append(f"fix_orientation:{rotation_applied}deg")

        # --- Step 3: Brightness / contrast ---
        img, brightness_delta, contrast_delta = adjust_brightness_contrast(img)
        steps_applied.append(
            f"clahe:brightness_delta={brightness_delta:.4f},contrast_delta={contrast_delta:.4f}"
        )

        # --- Step 4: Convert format ---
        img = convert_format(img, output_format)
        steps_applied.append(f"convert_format:{output_format}")

        metadata = {
            "resolution_dpi": effective_dpi,
            "rotation_applied": rotation_applied,
            "brightness_delta": brightness_delta,
            "contrast_delta": contrast_delta,
            "steps_applied": steps_applied,
            "output_format": output_format
        }
        return img, metadata

    except Exception as exc:
        logger.exception("In-memory pipeline unexpected error")
        if not isinstance(exc, PreprocessFailed | ImageDistorted | MemoryOverflow):
            raise PreprocessFailed(message=str(exc)) from exc
        raise


# ---------------------------------------------------------------------------
# 1. normalize_dpi
# ---------------------------------------------------------------------------


def normalize_dpi(
    img: np.ndarray,
    source_dpi: int,
    *,
    target_dpi: int = preprocess_settings.MIN_DPI,
    max_dimension: int = preprocess_settings.MAX_DIMENSION,
) -> tuple[np.ndarray, int]:
    """
    Resample *img* so its effective DPI equals *target_dpi*.

    If the image is already at or above the target DPI it is returned
    unchanged.  Images that would exceed *max_dimension* after upsampling
    are clamped to *max_dimension* to prevent memory issues.

    Parameters
    ----------
    img:
        Input BGR (or grayscale) image.
    source_dpi:
        The DPI metadata attached to the source scan.
    target_dpi:
        Desired output DPI (default: ``preprocess_settings.MIN_DPI``).
    max_dimension:
        Hard cap on the longest side of the output image in pixels.

    Returns
    -------
    resampled : np.ndarray
        The resampled image (same dtype as input).
    effective_dpi : int
        The DPI of the returned image.
    """
    try:
        if source_dpi <= 0:
            raise ValueError(f"source_dpi must be positive, got {source_dpi}")

        scale = target_dpi / source_dpi
        if scale <= 1.0:
            logger.debug("Source DPI %d >= target %d — no upsampling needed.", source_dpi, target_dpi)
            return img.copy(), source_dpi

        h, w = img.shape[:2]
        new_w = int(w * scale)
        new_h = int(h * scale)

        # Clamp to max_dimension
        longest = max(new_w, new_h)
        if longest > max_dimension:
            clamp_scale = max_dimension / longest
            new_w = int(new_w * clamp_scale)
            new_h = int(new_h * clamp_scale)
            effective_dpi = int(target_dpi * clamp_scale)
            logger.info(
                "Image clamped to %dx%d (max_dimension=%d); effective DPI=%d",
                new_w, new_h, max_dimension, effective_dpi,
            )
        else:
            effective_dpi = target_dpi

        resampled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        logger.info("Resampled %dx%d → %dx%d (DPI %d → %d)", w, h, new_w, new_h, source_dpi, effective_dpi)
        return resampled, effective_dpi

    except MemoryError as exc:
        raise MemoryOverflow() from exc
    except Exception as exc:  # noqa: BLE001
        raise PreprocessFailed(message=f"normalize_dpi failed: {exc}") from exc


# ---------------------------------------------------------------------------
# 2. fix_orientation
# ---------------------------------------------------------------------------

def fix_orientation(img: np.ndarray) -> tuple[np.ndarray, int]:
    """
    Auto-detect and correct the orientation of a text-document image.

    Detection uses (in priority order):
      1. **pytesseract OSD** — Tesseract's built-in Orientation & Script
         Detection; very reliable for printed text (requires ``tesseract``
         installed on the system).
      2. **Hough line analysis** — gradient-based skew estimation; works
         without Tesseract and corrects fine sub-degree tilts.
      3. **Histogram heuristic** — compares top/bottom ink density to catch
         180° flips when OSD is unavailable.

    Rotation is applied as follows:
      • Coarse multiples of 90° → :func:`cv2.rotate` (lossless, no cropping).
      • Fine skew angles         → :func:`cv2.getRotationMatrix2D` +
                                   :func:`cv2.warpAffine` with canvas expansion.

    Parameters
    ----------
    img:
        Input BGR (or grayscale) image as a numpy array.

    Returns
    -------
    corrected : np.ndarray
        The orientation-corrected image.
    rotation_applied : int
        Coarse rotation applied in degrees (0, 90, 180, or 270).
        Maps directly to ``PreprocessedImage.rotation_applied``.

    Raises
    ------
    ImageDistorted
        Raised when the image appears badly distorted and orientation
        cannot be reliably determined.
    PreprocessFailed
        Raised on any unexpected processing error.
    """
    try:
        if img is None or img.size == 0:
            raise ImageDistorted(message="fix_orientation received an empty image")

        corrected, rotation_applied = detect_and_correct_orientation(img)
        logger.info("fix_orientation complete — coarse rotation applied: %d°", rotation_applied)
        return corrected, rotation_applied

    except (ImageDistorted, PreprocessFailed):
        raise
    except MemoryError as exc:
        raise MemoryOverflow() from exc
    except Exception as exc:  # noqa: BLE001
        raise PreprocessFailed(message=f"fix_orientation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# 3. adjust_brightness_contrast
# ---------------------------------------------------------------------------

def adjust_brightness_contrast(
    img: np.ndarray,
    *,
    clip_limit: float = 2.0,
    tile_grid_size: tuple[int, int] = (8, 8),
) -> tuple[np.ndarray, float, float]:
    """
    Apply automatic adaptive contrast enhancement (CLAHE).

    CLAHE (Contrast Limited Adaptive Histogram Equalization) boosts local
    contrast without over-amplifying noise, making it well-suited for
    uneven-lighting scans and faded documents.

    Parameters
    ----------
    img:
        Input BGR (or grayscale) image.
    clip_limit:
        Threshold for contrast limiting.  Higher → stronger enhancement.
    tile_grid_size:
        Size of the grid for histogram equalization.

    Returns
    -------
    enhanced : np.ndarray
        The contrast-enhanced image (same colour space as input).
    brightness_delta : float
        Mean pixel value change (positive = brighter).
    contrast_delta : float
        Standard-deviation change (positive = more contrast).
    """
    try:
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

        if img.ndim == 2:
            # Grayscale
            before_mean = float(img.mean())
            before_std = float(img.std())
            enhanced = clahe.apply(img)
            after_mean = float(enhanced.mean())
            after_std = float(enhanced.std())
        else:
            # Colour — apply CLAHE only to the luminance (L) channel
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            before_mean = float(l_channel.mean())
            before_std = float(l_channel.std())
            l_eq = clahe.apply(l_channel)
            after_mean = float(l_eq.mean())
            after_std = float(l_eq.std())
            lab_eq = cv2.merge([l_eq, a_channel, b_channel])
            enhanced = cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)

        brightness_delta = round(after_mean - before_mean, 4)
        contrast_delta = round(after_std - before_std, 4)
        logger.info(
            "CLAHE — brightness Δ=%.4f  contrast Δ=%.4f",
            brightness_delta,
            contrast_delta,
        )
        return enhanced, brightness_delta, contrast_delta

    except MemoryError as exc:
        raise MemoryOverflow() from exc
    except Exception as exc:  # noqa: BLE001
        raise PreprocessFailed(message=f"adjust_brightness_contrast failed: {exc}") from exc


# ---------------------------------------------------------------------------
# 4. convert_format
# ---------------------------------------------------------------------------

_FORMAT_EXTENSIONS = {
    "png": ".png",
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "webp": ".webp",
    "tiff": ".tiff",
}

_ENCODE_PARAMS: dict[str, list[int]] = {
    "png": [cv2.IMWRITE_PNG_COMPRESSION, 3],
    "jpeg": [cv2.IMWRITE_JPEG_QUALITY, 95],
    "jpg": [cv2.IMWRITE_JPEG_QUALITY, 95],
    "webp": [cv2.IMWRITE_WEBP_QUALITY, 90],
    "tiff": [],
}


def convert_format(img: np.ndarray, output_format: str) -> np.ndarray:
    """
    Re-encode *img* into *output_format* and return the decoded result.

    This round-trip through encode/decode ensures the returned array
    exactly represents what would be written to disk, which is important
    for lossy formats (JPEG, WEBP) so downstream metrics are accurate.

    Parameters
    ----------
    img:
        Input BGR (or grayscale) image.
    output_format:
        Target format string, e.g. ``"png"``, ``"jpeg"``, ``"webp"``.

    Returns
    -------
    converted : np.ndarray
        The re-encoded/decoded image array.

    Raises
    ------
    PreprocessFailed
        If the format is unsupported or encoding fails.
    """
    fmt = output_format.lower().strip(".")
    if fmt not in _FORMAT_EXTENSIONS:
        supported = ", ".join(_FORMAT_EXTENSIONS)
        raise PreprocessFailed(
            message=f"Unsupported output format '{output_format}'. Supported: {supported}"
        )
    try:
        ext = _FORMAT_EXTENSIONS[fmt]
        params = _ENCODE_PARAMS.get(fmt, [])
        success, buffer = cv2.imencode(ext, img, params)
        if not success:
            raise RuntimeError("cv2.imencode returned False")
        converted = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)
        logger.info("Converted image to %s (%d bytes)", fmt.upper(), len(buffer))
        return converted
    except (PreprocessFailed, MemoryOverflow):
        raise
    except MemoryError as exc:
        raise MemoryOverflow() from exc
    except Exception as exc:  # noqa: BLE001
        raise PreprocessFailed(message=f"convert_format failed: {exc}") from exc
