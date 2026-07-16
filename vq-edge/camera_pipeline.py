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

# How many frames to discard before trusting the next capture.
WARMUP_FRAMES = 10


def _open_camera(camera_index: int, width: int, height: int) -> cv2.VideoCapture:
    """Open the camera using the same Windows-friendly settings as the working script."""
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open camera index {camera_index}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    return cap


def _flush_buffer(cap: cv2.VideoCapture, n: int = 3) -> None:
    """Discard a few buffered frames so the next read() isn't stale/in-motion."""
    for _ in range(n):
        cap.grab()


def capture_image_from_camera(
    camera_index: int,
    width: int = CAMERA_WIDTH,
    height: int = CAMERA_HEIGHT,
    warmup_frames: int = WARMUP_FRAMES,
    settle_seconds: float = FOCUS_SETTLE_SECONDS,
) -> np.ndarray:
    """
    Open the selected camera, set it to the target resolution, let
    autofocus/auto-exposure settle, then grab the latest full-resolution
    frame.

    Returns the captured frame as a BGR numpy array.
    """
    cap = _open_camera(camera_index, width, height)

    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[Camera] Opened at {actual_w}x{actual_h}")

        for _ in range(max(0, warmup_frames)):
            cap.read()

        time.sleep(settle_seconds)
        _flush_buffer(cap)

        ok, frame_bgr = cap.read()
        if not ok or frame_bgr is None:
            raise RuntimeError(f"Failed to capture any frame from camera index {camera_index}")

        print(f"[Camera] Captured frame at {actual_w}x{actual_h}")
        return frame_bgr
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
) -> dict:
    """
    Capture one high-resolution frame from the camera and hand it off to
    the main pipeline (background removal, anomaly detection, part
    detection, OCR) for processing.
    """
    frame_bgr = capture_image_from_camera(
        camera_index=camera_index,
        settle_seconds=settle_seconds,
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
        "--auto-run",
        action="store_true",
        help="Capture immediately and run the pipeline without waiting for manual input",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.auto_run:
        result = capture_and_run(
            camera_index=args.camera_index,
            output_image_path=args.output_image_path,
            settle_seconds=args.settle_seconds,
        )
        print("Pipeline result:")
        print(result)
        return

    result = capture_and_run(
        camera_index=args.camera_index,
        output_image_path=args.output_image_path,
        settle_seconds=args.settle_seconds,
    )
    print("Pipeline result:")
    print(result)


if __name__ == "__main__":
    main()