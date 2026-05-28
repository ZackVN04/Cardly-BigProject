"""
Preprocessing utility helpers.

Orientation detection strategy (in priority order):
1. pytesseract OSD  — fast, accurate for text-heavy scans (requires Tesseract).
2. Hough line analysis — gradient-based angle estimation, works without Tesseract.
3. Horizontal projection histogram — detects 180° flip by comparing top/bottom
   text density.

All public helpers are pure functions (numpy array in → numpy array / value out)
so they are easy to unit-test without a database or storage layer.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------
_SKEW_ANGLE_THRESHOLD = 0.5   # degrees — smaller than this is considered straight
_MAX_SKEW_CORRECTION = 45.0   # degrees — beyond this we trust 90/180/270 detection


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _to_gray(img: np.ndarray) -> np.ndarray:
    """Return a single-channel grayscale copy of *img* (no-op if already gray)."""
    if img.ndim == 2:
        return img.copy()
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _binarize(gray: np.ndarray) -> np.ndarray:
    """Adaptive threshold → binary image suitable for projection / Hough analysis."""
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    return binary


# ---------------------------------------------------------------------------
# Method 1 — pytesseract OSD (Orientation & Script Detection)
# ---------------------------------------------------------------------------

def _detect_orientation_osd(gray: np.ndarray) -> int | None:
    """
    Use Tesseract OSD to detect the dominant rotation (0, 90, 180, 270).

    Returns the rotation angle that should be applied to correct the image,
    or *None* when Tesseract is unavailable or OSD fails.
    """
    try:
        # pyrefly: ignore [missing-import]
        import pytesseract  # optional dependency

        osd = pytesseract.image_to_osd(gray, output_type=pytesseract.Output.DICT)
        rotate = int(osd.get("rotate", 0))
        confidence = float(osd.get("orientation_conf", 0))

        logger.debug("OSD rotate=%d  confidence=%.2f", rotate, confidence)

        # Tesseract reports the angle *already applied* by the scanner;
        # we need to apply the complement to bring it back to upright.
        if confidence >= 2.0 and rotate in (90, 180, 270):
            return rotate
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.debug("OSD unavailable or failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Method 2 — Gradient / Hough line analysis (skew angle estimation)
# ---------------------------------------------------------------------------

def _detect_skew_hough(gray: np.ndarray) -> float:
    """
    Estimate the fine skew angle (in degrees) via Canny edges + Hough lines.

    Returns a value in [-45, 45].  Positive → clockwise tilt.
    """
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=100,
        minLineLength=max(gray.shape[1] // 5, 50),
        maxLineGap=20,
    )
    if lines is None:
        return 0.0

    angles: list[float] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 == x1:
            continue  # vertical line — skip
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        # Keep only near-horizontal lines (text baseline candidates)
        if abs(angle) < 45:
            angles.append(angle)

    if not angles:
        return 0.0

    median_angle = float(np.median(angles))
    logger.debug("Hough skew estimate: %.2f°", median_angle)
    return median_angle


# ---------------------------------------------------------------------------
# Method 3 — Horizontal projection histogram (180° flip detection)
# ---------------------------------------------------------------------------

def _is_upside_down_histogram(binary: np.ndarray) -> bool:
    """
    Compare top-half vs bottom-half ink density to detect 180° inversion.

    In a correctly oriented text document the *top* rows typically contain
    more ink pixels than the *bottom* rows when averaged across bands
    (due to ascenders, caps, and page headers).  This heuristic works best
    on clean scans.
    """
    h = binary.shape[0]
    top_density = float(np.sum(binary[: h // 2])) / (h // 2)
    bottom_density = float(np.sum(binary[h // 2 :])) / (h // 2)
    ratio = bottom_density / top_density if top_density > 0 else 0
    print(f"Histogram density — top: {top_density:.2f}  bottom: {bottom_density:.2f}  ratio: {ratio:.4f}")
    logger.debug(
        "Histogram density — top: %.1f  bottom: %.1f", top_density, bottom_density
    )
    # bottom heavier → image is likely inverted
    return bottom_density > top_density * 1.05


# ---------------------------------------------------------------------------
# Public rotation helpers
# ---------------------------------------------------------------------------

def rotate_fixed(img: np.ndarray, angle: int) -> np.ndarray:
    """
    Rotate *img* by a multiple of 90° using cv2.rotate() — lossless, no cropping.

    Parameters
    ----------
    img:
        Input BGR (or grayscale) image.
    angle:
        One of 90, 180, 270.  0 returns a copy unchanged.
    """
    codes = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    if angle == 0:
        return img.copy()
    if angle not in codes:
        raise ValueError(f"angle must be one of 0/90/180/270, got {angle}")
    return cv2.rotate(img, codes[angle])


def rotate_arbitrary(img: np.ndarray, angle: float) -> np.ndarray:
    """
    Rotate *img* by an arbitrary angle while expanding the canvas to avoid cropping.

    Uses cv2.getRotationMatrix2D() + cv2.warpAffine() with INTER_CUBIC interpolation
    and a white background fill.

    Parameters
    ----------
    img:
        Input BGR (or grayscale) image.
    angle:
        Clockwise rotation in degrees (e.g. 3.5 corrects a –3.5° CCW tilt).
    """
    if abs(angle) < _SKEW_ANGLE_THRESHOLD:
        return img.copy()

    h, w = img.shape[:2]
    center = (w / 2.0, h / 2.0)

    M = cv2.getRotationMatrix2D(center, -angle, 1.0)  # negative → correct CW tilt

    # Expand output canvas so corners are not clipped
    cos_a = abs(M[0, 0])
    sin_a = abs(M[0, 1])
    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)

    # Adjust translation component
    M[0, 2] += (new_w - w) / 2.0
    M[1, 2] += (new_h - h) / 2.0

    border_color = (255, 255, 255) if img.ndim == 3 else 255
    rotated = cv2.warpAffine(
        img,
        M,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_color,
    )
    return rotated


# ---------------------------------------------------------------------------
# High-level orientation fix — combines all three methods
# ---------------------------------------------------------------------------

def detect_and_correct_orientation(img: np.ndarray) -> tuple[np.ndarray, int]:
    """
    Automatically detect and correct the orientation of a text-document image.

    Detection pipeline
    ------------------
    1. **pytesseract OSD** — detects coarse 90°/180°/270° rotation.
    2. **Hough line analysis** — estimates fine skew angle.
    3. **Histogram heuristic** — catches 180° flip when OSD is unavailable.

    Returns
    -------
    corrected : np.ndarray
        The straightened image (same dtype as input).
    total_rotation : int
        Total coarse rotation applied in degrees (0, 90, 180, or 270).
        Fine sub-degree corrections are not included in this integer.
    """
    gray = _to_gray(img)
    binary = _binarize(gray)

    # --- Step 1: coarse orientation via OSD ---
    coarse_rotation = _detect_orientation_osd(gray)

    if coarse_rotation is None:
        # Tesseract is not installed or failed. We use OpenCV-based projection profile analysis
        # to determine whether the text is oriented landscape (90 or 270) or portrait (0 or 180).
        # In text documents, the variance of horizontal projection profile is much higher
        # when lines of text are aligned horizontally (0 or 180 degrees) than vertically (90 or 270 degrees).
        
        # Test 0 degrees (original) vs 90 degrees
        h, w = binary.shape[:2]
        
        # 1. Detect if document is landscape-oriented text (90 or 270 degrees) vs portrait-oriented text (0 or 180 degrees)
        # Compute horizontal projection profile (mean of rows) to normalize against dimension differences
        proj_0 = np.mean(binary, axis=1)
        # For 90 degree rotation, the rows would be the columns of the original binary image
        proj_90 = np.mean(binary, axis=0)
        
        var_0 = np.var(proj_0)
        var_90 = np.var(proj_90)
        
        # In a text document, the profile with higher variance corresponds to the text lines aligned with the axis.
        # If var_90 is significantly larger than var_0, the text runs vertically, meaning a 90 or 270 degree rotation is needed.
        is_landscape_text = var_90 > var_0
        
        print(
            f"OpenCV orientation check: var_0 (portrait var) = {var_0:.2f}, var_90 (landscape var) = {var_90:.2f}. is_landscape_text = {is_landscape_text}"
        )
        
        if is_landscape_text:
            # It is rotated 90 or 270 degrees. To decide between 90 and 270, we check the margins or column ink density.
            # Let's rotate 90 degrees first and check if it's upside down.
            img_90 = rotate_fixed(img, 90)
            binary_90 = _binarize(_to_gray(img_90))
            is_upside_down = _is_upside_down_histogram(binary_90)
            print(f"Landscape check: rotating 90 deg. is_upside_down = {is_upside_down}")
            coarse_rotation = 270 if is_upside_down else 90
            print(
                f"OSD not available; projection variance analysis → landscape text detected, coarse rotation={coarse_rotation}°"
            )
        else:
            # It is oriented 0 or 180 degrees.
            is_upside_down = _is_upside_down_histogram(binary)
            print(f"Portrait check: is_upside_down = {is_upside_down}")
            coarse_rotation = 180 if is_upside_down else 0
            print(
                f"OSD not available; projection variance analysis → portrait text detected, coarse rotation={coarse_rotation}°"
            )
    else:
        print(f"OSD → coarse rotation={coarse_rotation}°")

    corrected = rotate_fixed(img, coarse_rotation) if coarse_rotation != 0 else img.copy()

    # --- Step 2: fine skew correction via Hough ---
    gray_corrected = _to_gray(corrected)
    skew_angle = _detect_skew_hough(gray_corrected)

    if abs(skew_angle) >= _SKEW_ANGLE_THRESHOLD and abs(skew_angle) <= _MAX_SKEW_CORRECTION:
        logger.info("Applying fine skew correction: %.2f°", skew_angle)
        corrected = rotate_arbitrary(corrected, skew_angle)
    else:
        logger.debug("Skew angle %.2f° below threshold — skipped", skew_angle)

    return corrected, coarse_rotation
