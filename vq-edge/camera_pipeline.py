from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from main import (
    run_single_frame,
    ANOMALY_MODEL_PATH,
    RFDETR_MODEL_PATH,
    OCR_MODEL_DIR,
    ANOMALY_THRESHOLD,
    MASK_THRESHOLD,
    MIN_AREA,
    RFDETR_THRESHOLD,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
)

# How long to let autofocus / auto-exposure settle after opening the camera
# or after re-triggering focus, before we trust any frame.
FOCUS_SETTLE_SECONDS = 1.5

# Number of candidate frames to compare (by sharpness) once settled.
CANDIDATE_FRAMES = 5

# Laplacian-variance threshold below which a frame is considered blurry.
# This is scene-dependent — tune it against a few real captures. Printed
# to the console on every capture so you can calibrate it.
MIN_SHARPNESS = 60.0

# If every candidate frame comes back blurry, how many extra times to
# re-settle and try again before giving up.
MAX_RETRIES = 2


def _sharpness_score(frame_bgr: np.ndarray) -> float:
    """
    Focus/sharpness metric: variance of the Laplacian. Higher = sharper.
    Computed on a grayscale, moderately downscaled copy for speed.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    if max(h, w) > 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _flush_buffer(cap: cv2.VideoCapture, n: int = 3) -> None:
    """Discard a few buffered frames so the next read() isn't stale/in-motion."""
    for _ in range(n):
        cap.grab()


def capture_image_from_camera(
    camera_index: int,
    width: int = CAMERA_WIDTH,
    height: int = CAMERA_HEIGHT,
    warmup_frames: int = 10,
    settle_seconds: float = FOCUS_SETTLE_SECONDS,
    candidate_frames: int = CANDIDATE_FRAMES,
    min_sharpness: float = MIN_SHARPNESS,
    max_retries: int = MAX_RETRIES,
) -> np.ndarray:
    """
    Open the selected camera, set it to the target resolution, give
    autofocus/auto-exposure time to settle, then grab several candidate
    frames and keep the sharpest one.

    Returns the captured frame as a BGR numpy array.
    """
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        raise RuntimeError(f"Unable to open camera index {camera_index}")

    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[Camera] Opened at {actual_w}x{actual_h}")

        for _ in range(max(0, warmup_frames)):
            cap.read()

        best_frame: np.ndarray | None = None
        best_score = -1.0

        for attempt in range(max_retries + 1):
            # Let autofocus / auto-exposure converge before trusting frames.
            time.sleep(settle_seconds)
            _flush_buffer(cap)

            for _ in range(candidate_frames):
                ok, frame_bgr = cap.read()
                if not ok or frame_bgr is None:
                    continue
                score = _sharpness_score(frame_bgr)
                if score > best_score:
                    best_score = score
                    best_frame = frame_bgr

            print(f"[Camera] Attempt {attempt + 1}: best sharpness score = {best_score:.1f}")

            if best_score >= min_sharpness:
                break

            if attempt < max_retries:
                print("[Camera] Frame below sharpness threshold, re-triggering focus and retrying...")
                # Re-trigger autofocus by toggling it off/on.
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

        if best_frame is None:
            raise RuntimeError(f"Failed to capture any frame from camera index {camera_index}")

        if best_score < min_sharpness:
            print(
                f"[Camera] Warning: best frame scored {best_score:.1f}, "
                f"below the sharpness threshold of {min_sharpness:.1f}. Using it anyway."
            )

        print(f"[Camera] Captured frame at {actual_w}x{actual_h} (sharpness={best_score:.1f})")
        return best_frame
    finally:
        cap.release()


def save_frame(frame_bgr: np.ndarray, output_path: str | Path | None = None) -> str:
    """Save a captured frame to disk and return the absolute path."""
    if output_path is None:
        output_path = Path(tempfile.gettempdir()) / "captured_frame.png"

    output_path = str(Path(output_path).resolve())
    if not cv2.imwrite(output_path, frame_bgr):
        raise RuntimeError(f"Failed to save captured image to {output_path}")

    print(f"[Camera] Saved frame to {output_path}")
    return output_path


def capture_and_run(
    camera_index: int = 0,
    output_image_path: str | Path | None = None,
    settle_seconds: float = FOCUS_SETTLE_SECONDS,
    candidate_frames: int = CANDIDATE_FRAMES,
    min_sharpness: float = MIN_SHARPNESS,
) -> dict:
    """
    Capture one high-resolution frame from the camera and hand it off to
    the main pipeline (background removal, anomaly detection, part
    detection, OCR) for processing.
    """
    frame_bgr = capture_image_from_camera(
        camera_index=camera_index,
        settle_seconds=settle_seconds,
        candidate_frames=candidate_frames,
        min_sharpness=min_sharpness,
    )

    if output_image_path is not None:
        save_frame(frame_bgr, output_image_path)

    return run_single_frame(
        frame_bgr=frame_bgr,
        anomaly_model_path=ANOMALY_MODEL_PATH,
        rfdetr_model_path=RFDETR_MODEL_PATH,
        ocr_model_dir=OCR_MODEL_DIR,
        anomaly_threshold=ANOMALY_THRESHOLD,
        mask_threshold=MASK_THRESHOLD,
        min_area=MIN_AREA,
        rfdetr_threshold=RFDETR_THRESHOLD,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a high-resolution image from the camera and run it through the pipeline",
    )
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index (default: 0)")
    parser.add_argument(
        "--output-image-path",
        type=str,
        default=None,
        help="Optional path to save the captured image",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=FOCUS_SETTLE_SECONDS,
        help="Seconds to wait for autofocus/auto-exposure to settle (default: %(default)s)",
    )
    parser.add_argument(
        "--candidate-frames",
        type=int,
        default=CANDIDATE_FRAMES,
        help="Number of frames to compare by sharpness per attempt (default: %(default)s)",
    )
    parser.add_argument(
        "--min-sharpness",
        type=float,
        default=MIN_SHARPNESS,
        help="Laplacian-variance sharpness threshold (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = capture_and_run(
        camera_index=args.camera_index,
        output_image_path=args.output_image_path,
        settle_seconds=args.settle_seconds,
        candidate_frames=args.candidate_frames,
        min_sharpness=args.min_sharpness,
    )
    print("Pipeline result:")
    print(result)


if __name__ == "__main__":
    main()