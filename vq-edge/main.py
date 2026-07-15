from __future__ import annotations

import base64
import threading
import time
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from rembg import remove, new_session
import uvicorn
from fastapi import FastAPI

from engine.anomaly_engine import AnomalyEngine
from engine.rfdetr_engine import RFDETREngine
# ✓ FIXED: Import corrected OCR engine and extraction helper
from engine.ocr_engine import OCR_Engine, run_ocr


# ---------------------------------------------------------------------------
# Runtime configuration
# ---------------------------------------------------------------------------
CAMERA_INDEX = 0
ANOMALY_MODEL_PATH = r"C:\Users\medhavyn\OneDrive - Medhavyn Technologies (1)\Dhananjay Odhekar's files - VisionQ-Training-Datasets\rangavishwa\ckpt-models\raen_crompton_anomaly_new.ckpt"
RFDETR_MODEL_PATH = r"C:\Users\medhavyn\OneDrive - Medhavyn Technologies (1)\Dhananjay Odhekar's files - VisionQ-Training-Datasets\bill-industries\models-rfdetr\biin_0101ES200600N.pth"
OCR_MODEL_DIR: str | None = None
ANOMALY_THRESHOLD = 0.5
MASK_THRESHOLD = 128
MIN_AREA = 50
RFDETR_THRESHOLD = 0.7
OCR_MIN_CONFIDENCE = 0.75

API_HOST = "0.0.0.0"
API_PORT = 8001

# Camera capture resolution (set to match your camera's native resolution)
CAMERA_WIDTH = 3840
CAMERA_HEIGHT = 2160

# How long to wait between successive pipeline runs (seconds).
LOOP_INTERVAL = 0.5

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
rembg_session = new_session()
app = FastAPI(title="VQ Edge Inspection Backend", version="1.0.0")


class InspectionState:
    """Thread-safe state for the continuous inspection loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status: str = "idle"  # idle | scanning | paused | finished
        self._latest_result: dict[str, Any] | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()  # Set = NOT paused (run), Clear = paused
        self._pause_event.set()

    # --- status ---
    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @status.setter
    def status(self, value: str) -> None:
        with self._lock:
            self._status = value

    # --- latest result ---
    @property
    def latest_result(self) -> dict[str, Any] | None:
        with self._lock:
            return self._latest_result

    @latest_result.setter
    def latest_result(self, value: dict[str, Any] | None) -> None:
        with self._lock:
            self._latest_result = value

    # --- lifecycle ---
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            # Already running — just unpause
            self._pause_event.set()
            self.status = "scanning"
            return

        self._stop_event.clear()
        self._pause_event.set()
        self.status = "scanning"
        self.latest_result = None

        self._thread = threading.Thread(target=_inspection_loop, args=(self,), daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self._pause_event.clear()
        self.status = "paused"

    def resume(self) -> None:
        self._pause_event.set()
        self.status = "scanning"

    def finish(self) -> None:
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused so thread can exit
        self.status = "finished"
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    @property
    def should_stop(self) -> bool:
        return self._stop_event.is_set()

    def wait_if_paused(self) -> None:
        """Block until unpaused, or return immediately if not paused."""
        self._pause_event.wait()


inspection_state = InspectionState()


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------
def remove_background(image_rgb: np.ndarray):
    print("Removing background...")
    result_rgba = remove(image_rgb, session=rembg_session)
    alpha = result_rgba[..., 3:4].astype(np.float32) / 255.0
    rgb = result_rgba[..., :3].astype(np.float32)
    background = np.zeros((1, 1, 3), dtype=np.float32)
    result_rgb = (rgb * alpha + background * (1.0 - alpha)).astype(np.uint8)
    print("Background removal completed.")
    return result_rgba, result_rgb


def _normalize_bbox(box: Any, image_w: int, image_h: int) -> tuple[int, int, int, int] | None:
    """Convert PaddleOCR box formats into a clamped x1, y1, x2, y2 rectangle."""
    try:
        box_array = np.array(box)

        if box_array.ndim == 2 and box_array.shape[1] == 2:
            x1 = int(box_array[:, 0].min())
            y1 = int(box_array[:, 1].min())
            x2 = int(box_array[:, 0].max())
            y2 = int(box_array[:, 1].max())
        elif box_array.ndim == 1 and len(box_array) == 4:
            x1, y1, x2, y2 = [int(v) for v in box_array]
        else:
            return None

        x1 = max(0, min(x1, image_w))
        y1 = max(0, min(y1, image_h))
        x2 = max(0, min(x2, image_w))
        y2 = max(0, min(y2, image_h))

        if x2 <= x1 or y2 <= y1:
            return None

        return x1, y1, x2, y2
    except Exception:
        return None


def _encode_image_to_base64_png(image: np.ndarray | None) -> str | None:
    if image is None or image.size == 0:
        return None
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("ascii")


# ---------------------------------------------------------------------------
# OCR annotation helper
# ---------------------------------------------------------------------------
def _annotate_ocr_lines(
    image_bgr: np.ndarray, 
    ocr_lines: list[dict[str, Any]]
) -> np.ndarray:
    """
    Draw green bounding boxes and text labels on the image for each OCR detection.
    
    Args:
        image_bgr: Input image in BGR format (will be copied before modification)
        ocr_lines: List of OCR results from extract_ocr_lines() with 'text' and 'box' keys
        
    Returns:
        Annotated image with drawn boxes and text labels
    """
    annotated = image_bgr.copy()
    
    if not ocr_lines:
        return annotated

    img_h, img_w = annotated.shape[:2]
    
    for line in ocr_lines:
        text = line.get("text", "")
        box = line.get("box")
        score = line.get("score")
        
        normalized_box = _normalize_bbox(box, img_w, img_h)
        if normalized_box is None:
            continue
        
        try:
            bx1, by1, bx2, by2 = normalized_box
            
            # Draw green rectangle around detected text
            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
            
            # Prepare label text with confidence score if available
            label = text
            if score is not None:
                label = f"{text} ({score:.2f})"
            
            # Draw semi-transparent background for text readability
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            
            # Position text above the box
            text_x = bx1
            text_y = max(by1 - 5, 15)
            
            # Draw black background for text
            cv2.rectangle(
                annotated,
                (text_x - 2, text_y - text_h - 2),
                (text_x + text_w + 2, text_y + baseline + 2),
                (0, 0, 0),
                -1
            )
            
            # Draw white text
            cv2.putText(
                annotated, 
                label,
                (text_x, text_y),
                font, 
                font_scale, 
                (255, 255, 255), 
                thickness
            )
            
        except Exception as e:
            print(f"[OCR Annotation] Error drawing box {box}: {e}")
            continue
    
    return annotated


def _ocr_lines_to_boxes(
    ocr_lines: list[dict[str, Any]],
    image_w: int,
    image_h: int,
) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []

    for idx, line in enumerate(ocr_lines):
        normalized_box = _normalize_bbox(line.get("box"), image_w, image_h)
        if normalized_box is None:
            continue

        x1, y1, x2, y2 = normalized_box
        boxes.append(
            {
                "id": f"ocr-{idx + 1}",
                "text": line.get("text", ""),
                "status": "correct",
                "top": (y1 / image_h) * 100.0 if image_h > 0 else 0.0,
                "left": (x1 / image_w) * 100.0 if image_w > 0 else 0.0,
                "width": ((x2 - x1) / image_w) * 100.0 if image_w > 0 else 0.0,
                "height": ((y2 - y1) / image_h) * 100.0 if image_h > 0 else 0.0,
            }
        )

    return boxes


# ---------------------------------------------------------------------------
# Pipeline: single frame
# ---------------------------------------------------------------------------
def run_single_frame(
    frame_bgr: np.ndarray,
    anomaly_model_path: str,
    rfdetr_model_path: str,
    ocr_model_dir: str | None = None,
    anomaly_threshold: float = 0.5,
    mask_threshold: int = 128,
    min_area: int = 50,
    rfdetr_threshold: float = 0.7,
) -> dict[str, Any]:
    """
    Run the full pipeline on a single captured frame:
      1. Remove background
      2. Anomaly detection (on bg-removed image)
      3. Part detection (RF-DETR) + crop (on original frame)
      4. OCR on the cropped region
    Returns a dict ready to be sent to the frontend.
    """
    image_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    # Step 1: Remove background
    _, image_rgb_no_bg = remove_background(image_rgb)

    # Step 2: Anomaly detection on bg-removed image
    anomaly_engine = AnomalyEngine()
    anomaly_result = anomaly_engine._detect_anomaly(
        image_rgb=image_rgb_no_bg,
        anomaly_model_path=anomaly_model_path,
        anomaly_threshold=anomaly_threshold,
        mask_threshold=mask_threshold,
        min_area=min_area,
    )

    # Step 3: Part detection (RF-DETR) on original frame
    rfdetr_engine = RFDETREngine(
        model_path=rfdetr_model_path,
        threshold=rfdetr_threshold,
    )
    part_result = rfdetr_engine.detect_part(frame_bgr)

    # Step 4: OCR on cropped part
    # ✓ FIXED: Use corrected OCR engine with proper configuration
    ocr_lines = []
    if part_result is not None:
        crop_bgr = part_result["crop"]
        if crop_bgr.size > 0:
            ocr_engine = OCR_Engine(model_dir=ocr_model_dir, device="gpu:0")
            ocr_result = run_ocr(crop_bgr, ocr_engine)
            ocr_lines = ocr_result["lines"]
            
            # Debug: log the extracted OCR lines
            print(f"[Pipeline] Extracted {len(ocr_lines)} OCR lines from crop")
            for i, line in enumerate(ocr_lines):
                print(f"  Line {i}: text='{line['text']}', box={line.get('box')}, score={line.get('score'):.3f}")

    # Build the response payload
    return _build_payload(frame_bgr, anomaly_result, part_result, ocr_lines)


def _build_payload(
    image_bgr: np.ndarray,
    anomaly_result: dict,
    part_result: dict | None,
    ocr_lines: list[dict[str, Any]],  # ✓ FIXED: Now expects structured list
) -> dict[str, Any]:
    """
    Build a JSON-serialisable payload from pipeline results.

    The displayed image is the **crop** of the detected part with:
      - Anomaly heatmap overlay (when anomaly detected)
      - Green bounding boxes around each OCR-detected text region with labels
    """
    image_h, image_w = image_bgr.shape[:2]

    anomaly = anomaly_result or {}
    anomaly_results = anomaly.get("results") or []
    anomaly_count = len(anomaly_results)
    anomaly_score = float(anomaly.get("score", 0.0) or 0.0)
    anomaly_label = int(anomaly.get("label", 0) or 0)

    # ---- Build the annotated crop image ----
    has_crop = (
        isinstance(part_result, dict)
        and part_result.get("crop") is not None
        and part_result["crop"].size > 0
    )

    if has_crop:
        crop = part_result["crop"]
        part_bbox = part_result.get("bbox")  # (x1, y1, x2, y2) in full-frame coords
        annotated = crop.copy()
        crop_h, crop_w = annotated.shape[:2]

        print(f"[Build Payload] Crop size: {crop_w}x{crop_h}, Anomaly count: {anomaly_count}, OCR lines: {len(ocr_lines)}")

        # --- Anomaly heatmap on crop (only when anomaly detected) ---
        mask = anomaly.get("mask")
        if isinstance(mask, np.ndarray) and mask.size > 0 and anomaly_count > 0:
            print("[Build Payload] Applying anomaly heatmap overlay...")
            if len(mask.shape) == 3:
                mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            if mask.shape[:2] != (image_h, image_w):
                mask = cv2.resize(mask, (image_w, image_h), interpolation=cv2.INTER_LINEAR)

            # Crop the anomaly map to the detected part region
            px1, py1, px2, py2 = [int(v) for v in part_bbox]
            mask_crop = mask[py1:py2, px1:px2]
            if mask_crop.shape[:2] != (crop_h, crop_w):
                mask_crop = cv2.resize(mask_crop, (crop_w, crop_h), interpolation=cv2.INTER_LINEAR)

            heatmap = cv2.applyColorMap(mask_crop.astype(np.uint8), cv2.COLORMAP_JET)

            # Per-pixel alpha — only overlay where anomaly values are significant
            alpha = np.zeros((crop_h, crop_w), dtype=np.float32)
            alpha[mask_crop.astype(np.float32) > 30] = 0.45
            alpha_3ch = np.stack([alpha] * 3, axis=-1)
            annotated = (
                annotated.astype(np.float32) * (1 - alpha_3ch)
                + heatmap.astype(np.float32) * alpha_3ch
            ).astype(np.uint8)

        # --- ✓ FIXED: Draw green bounding boxes for OCR text using helper function ---
        if ocr_lines:
            print(f"[Build Payload] Drawing {len(ocr_lines)} OCR bounding boxes on crop...")
            annotated = _annotate_ocr_lines(annotated, ocr_lines)
        else:
            print("[Build Payload] No OCR lines to annotate")

        boxes = _ocr_lines_to_boxes(ocr_lines, crop_w, crop_h)

        captured_image_b64 = _encode_image_to_base64_png(annotated)
        print("[Build Payload] Annotated crop encoded to PNG and base64")
    else:
        # No crop available — show the raw camera frame
        print("[Build Payload] No crop available, using raw frame")
        captured_image_b64 = _encode_image_to_base64_png(image_bgr)
        boxes = []

    # ---- Compute summary stats ----
    total = len(ocr_lines)
    if total == 0 and anomaly_count > 0:
        total = anomaly_count
    rejected = min(total, anomaly_count) if total > 0 else anomaly_count
    accepted = max(0, total - rejected)

    wrong_text = []
    if anomaly_count > 0:
        wrong_text.append({
            "text": "Anomaly region detected",
            "reason": f"score={anomaly_score:.3f}",
        })

    # Strip internal box coords before sending to frontend
    # ✓ FIXED: Keep only text and score, remove box from frontend payload
    frontend_ocr = [{"text": l["text"], "score": l.get("score")} for l in ocr_lines]

    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "wrongText": wrong_text,
        "boxes": boxes,
        "ocrLines": frontend_ocr,
        "anomaly": {
            "label": anomaly_label,
            "score": anomaly_score,
            "count": anomaly_count,
        },
        "capturedImageBase64": captured_image_b64,
    }


def _make_empty_result(error: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "total": 0,
        "accepted": 0,
        "rejected": 0,
        "wrongText": [],
        "boxes": [],
        "ocrLines": [],
        "anomaly": {
            "label": 0,
            "score": 0.0,
            "count": 0,
        },
        "capturedImageBase64": None,
    }
    if error:
        result["error"] = error
    return result


# ---------------------------------------------------------------------------
# Continuous inspection loop (runs in a background thread)
# ---------------------------------------------------------------------------
def _inspection_loop(state: InspectionState) -> None:
    """
    Continuously capture frames and run the ML pipeline until stopped.

    The camera stays open for the entire session (no open/close per frame).
    """
    print(f"[Inspection Loop] Opening camera index {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        error_msg = f"Camera not available (index {CAMERA_INDEX})"
        print(f"[Inspection Loop] {error_msg}")
        state.latest_result = _make_empty_result(error=error_msg)
        state.status = "idle"
        return

    # Set 4K resolution and optimal capture settings
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # Always grab the latest frame
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)    # Enable autofocus

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[Inspection Loop] Camera resolution: {actual_w}x{actual_h}")

    # Warmup frames (let auto-exposure settle)
    for _ in range(10):
        cap.read()

    print("[Inspection Loop] Camera ready. Starting continuous inspection...")
    frame_count = 0

    try:
        while not state.should_stop:
            # Block here if paused
            state.wait_if_paused()
            if state.should_stop:
                break

            ok, frame_bgr = cap.read()
            if not ok or frame_bgr is None:
                print("[Inspection Loop] Failed to capture frame, retrying...")
                time.sleep(0.5)
                continue

            frame_count += 1
            print(f"\n[Inspection Loop] Processing frame #{frame_count}...")

            try:
                result = run_single_frame(
                    frame_bgr=frame_bgr,
                    anomaly_model_path=ANOMALY_MODEL_PATH,
                    rfdetr_model_path=RFDETR_MODEL_PATH,
                    ocr_model_dir=OCR_MODEL_DIR,
                    anomaly_threshold=ANOMALY_THRESHOLD,
                    mask_threshold=MASK_THRESHOLD,
                    min_area=MIN_AREA,
                    rfdetr_threshold=RFDETR_THRESHOLD,
                )
                result["frameNumber"] = frame_count
                state.latest_result = result

                # Check if anomaly/wrong part detected
                anomaly_count = result.get("anomaly", {}).get("count", 0)
                if anomaly_count > 0:
                    print(f"[Inspection Loop] ⚠ Anomaly detected on frame #{frame_count}! "
                          f"Pausing for review.")
                    state.status = "paused"
                    state._pause_event.clear()
                    # Don't break — user can resume after reviewing

            except Exception as exc:
                print(f"[Inspection Loop] Pipeline error on frame #{frame_count}: {exc}")
                import traceback
                traceback.print_exc()  # ✓ FIXED: Added traceback for debugging
                error_result = _make_empty_result(error=f"Pipeline error: {exc}")
                # Encode the raw frame so the user can at least see what was captured
                error_result["capturedImageBase64"] = _encode_image_to_base64_png(frame_bgr)
                error_result["frameNumber"] = frame_count
                state.latest_result = error_result

            # Small delay between frames so we don't spin the GPU at 100%
            time.sleep(LOOP_INTERVAL)

    finally:
        cap.release()
        print(f"[Inspection Loop] Camera released. Processed {frame_count} frames total.")


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "vq-edge-python-backend"}


@app.post("/inspect/start")
def inspect_start() -> dict[str, Any]:
    """Start or resume continuous inspection."""
    if inspection_state.status == "scanning":
        return {"status": "scanning", "message": "Inspection already running."}

    inspection_state.start()
    return {"status": "scanning", "message": "Inspection started."}


@app.post("/inspect/pause")
def inspect_pause() -> dict[str, Any]:
    """Pause continuous inspection (camera stays open)."""
    inspection_state.pause()
    return {"status": "paused"}


@app.post("/inspect/resume")
def inspect_resume() -> dict[str, Any]:
    """Resume a paused inspection."""
    inspection_state.resume()
    return {"status": "scanning", "message": "Inspection resumed."}


@app.post("/inspect/finish")
def inspect_finish() -> dict[str, Any]:
    """Stop inspection and release the camera."""
    inspection_state.finish()
    return {"status": "finished"}


@app.get("/inspect/latest")
def inspect_latest() -> dict[str, Any]:
    """Return the latest inspection result and current status."""
    result = inspection_state.latest_result
    return {
        "status": inspection_state.status,
        "result": result,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=False)