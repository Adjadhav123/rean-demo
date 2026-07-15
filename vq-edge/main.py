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
from engine.ocr_engine import OCR_Engine


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


def _encode_image_to_base64_png(image: np.ndarray | None) -> str | None:
    if image is None or image.size == 0:
        return None
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _extract_ocr_lines(node: Any, min_confidence: float = 0.0) -> list[dict[str, Any]]:
    """Walk OCR results and return [{text, score, box}, ...]."""
    lines: list[dict[str, Any]] = []

    def _parse_box(raw_box: Any) -> list[int] | None:
        """Convert a polygon or rect box to [x1, y1, x2, y2]."""
        try:
            arr = np.array(raw_box)
            if arr.ndim == 2:
                return [
                    int(arr[:, 0].min()), int(arr[:, 1].min()),
                    int(arr[:, 0].max()), int(arr[:, 1].max()),
                ]
            if arr.ndim == 1 and len(arr) == 4:
                return list(map(int, arr))
        except Exception:
            pass
        return None

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            rec_texts = value.get("rec_texts")
            rec_scores = value.get("rec_scores")
            rec_boxes = value.get("rec_boxes")
            if isinstance(rec_texts, list):
                for idx, text in enumerate(rec_texts):
                    if not isinstance(text, str):
                        continue
                    score = None
                    if isinstance(rec_scores, list) and idx < len(rec_scores):
                        try:
                            score = float(rec_scores[idx])
                        except Exception:
                            score = None
                    box = None
                    if isinstance(rec_boxes, list) and idx < len(rec_boxes):
                        box = _parse_box(rec_boxes[idx])
                    lines.append({"text": text, "score": score, "box": box})

            if isinstance(value.get("text"), str):
                score = value.get("score")
                try:
                    score = float(score) if score is not None else None
                except Exception:
                    score = None
                lines.append({"text": value["text"], "score": score, "box": None})

            for child in value.values():
                walk(child)
            return

        if isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk(node)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in lines:
        text = line.get("text", "").strip()
        if not text:
            continue
        key = f"{text}|{line.get('score')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"text": text, "score": line.get("score"), "box": line.get("box")})
    if min_confidence > 0:
        deduped = [line for line in deduped if line.get("score") is not None and line["score"] >= min_confidence]
    return deduped


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
    ocr_result = None
    if part_result is not None:
        crop_bgr = part_result["crop"]
        if crop_bgr.size > 0:
            ocr_engine = OCR_Engine(model_dir=ocr_model_dir)
            ocr_result = ocr_engine.predict(crop_bgr)

    # Build the response payload
    return _build_payload(frame_bgr, anomaly_result, part_result, ocr_result)


def _build_payload(
    image_bgr: np.ndarray,
    anomaly_result: dict,
    part_result: dict | None,
    ocr_raw: Any,
) -> dict[str, Any]:
    """
    Build a JSON-serialisable payload from pipeline results.

    The displayed image is the **crop** of the detected part with:
      - Anomaly heatmap overlay (when anomaly detected)
      - Green bounding boxes around each OCR-detected text region
    """
    image_h, image_w = image_bgr.shape[:2]

    anomaly = anomaly_result or {}
    anomaly_results = anomaly.get("results") or []
    anomaly_count = len(anomaly_results)
    anomaly_score = float(anomaly.get("score", 0.0) or 0.0)
    anomaly_label = int(anomaly.get("label", 0) or 0)

    ocr_lines = _extract_ocr_lines(ocr_raw, min_confidence=OCR_MIN_CONFIDENCE)

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

        # --- Anomaly heatmap on crop (only when anomaly detected) ---
        mask = anomaly.get("mask")
        if isinstance(mask, np.ndarray) and mask.size > 0 and anomaly_count > 0:
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

        # --- Green bounding boxes for OCR text ---
        for line in ocr_lines:
            box = line.get("box")
            if box and len(box) == 4:
                bx1, by1, bx2, by2 = [int(v) for v in box]
                cv2.rectangle(annotated, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                cv2.putText(
                    annotated, line["text"],
                    (bx1, max(by1 - 5, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1,
                )

        captured_image_b64 = _encode_image_to_base64_png(annotated)
    else:
        # No crop available — show the raw camera frame
        captured_image_b64 = _encode_image_to_base64_png(image_bgr)

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
    frontend_ocr = [{"text": l["text"], "score": l.get("score")} for l in ocr_lines]

    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "wrongText": wrong_text,
        "boxes": [],
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
