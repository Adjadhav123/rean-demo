from __future__ import annotations

import base64
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from rembg import remove, new_session
import uvicorn
from fastapi import FastAPI, HTTPException

from engine.anomaly_engine import AnomalyEngine
from engine.rfdetr_engine import RFDETREngine
from engine.ocr_engine import OCR_Engine


# Hardcoded runtime configuration requested by user.
CAMERA_INDEX = 0
ANOMALY_MODEL_PATH = "C:/models/anomaly_model.ckpt"
RFDETR_MODEL_PATH = "C:/models/rfdetr_model.pth"
OCR_MODEL_DIR: str | None = None
ANOMALY_THRESHOLD = 0.5
MASK_THRESHOLD = 128
MIN_AREA = 50
RFDETR_THRESHOLD = 0.7

CAPTURED_IMAGE_PATH = str(Path(tempfile.gettempdir()) / "captured_frame.png")

API_HOST = "0.0.0.0"
API_PORT = 8001


rembg_session = new_session()
app = FastAPI(title="VQ Edge Inspection Backend", version="1.0.0")


@dataclass(frozen=True)
class PipelineConfig:
    image_path: str
    anomaly_model_path: str
    rfdetr_model_path: str
    ocr_model_dir: str | None = None
    anomaly_threshold: float = 0.5
    mask_threshold: int = 128
    min_area: int = 50
    rfdetr_threshold: float = 0.7


def remove_background(image_rgb: np.ndarray):
    """
    Remove background from image using rembg.

    Args:
        image_rgb: Input image in RGB format

    Returns:
        Tuple of (image_rgba, image_rgb_with_background)
        - image_rgba: RGBA image with transparency
        - image_rgb_with_background: RGB image with custom background
    """
    print("Removing background...")

    result_rgba = remove(image_rgb, session=rembg_session)

    alpha = result_rgba[..., 3:4].astype(np.float32) / 255.0
    rgb = result_rgba[..., :3].astype(np.float32)

    background = np.zeros((1, 1, 3), dtype=np.float32)

    result_rgb = (rgb * alpha + background * (1.0 - alpha)).astype(np.uint8)

    print("Background removal completed.")
    return result_rgba, result_rgb


def load_image(image_path: str) -> np.ndarray:
	image_bgr = cv2.imread(image_path)
	if image_bgr is None:
		raise FileNotFoundError(f"Unable to read image: {image_path}")
	return image_bgr


def capture_image_from_camera(
	camera_index: int,
	output_path: str | Path,
	warmup_frames: int = 10,
) -> str:
	cap = cv2.VideoCapture(camera_index)
	if not cap.isOpened():
		raise RuntimeError(f"Unable to open camera index {camera_index}")

	try:
		for _ in range(max(0, warmup_frames)):
			cap.read()

		ok, frame_bgr = cap.read()
		if not ok or frame_bgr is None:
			raise RuntimeError(f"Failed to capture frame from camera index {camera_index}")

		output_path = str(Path(output_path).resolve())
		saved = cv2.imwrite(output_path, frame_bgr)
		if not saved:
			raise RuntimeError(f"Failed to save captured image to {output_path}")

		return output_path
	finally:
		cap.release()


def run_pipeline(
	image_path: str,
	anomaly_model_path: str,
	rfdetr_model_path: str,
	ocr_model_dir: str | None = None,
	anomaly_threshold: float = 0.5,
	mask_threshold: int = 128,
	min_area: int = 50,
	rfdetr_threshold: float = 0.7,
):
	image_bgr = load_image(image_path)
	image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

	_, image_rgb_no_bg = remove_background(image_rgb)

	anomaly_engine = AnomalyEngine()
	anomaly_result = anomaly_engine._detect_anomaly(
		image_rgb=image_rgb_no_bg,
		anomaly_model_path=anomaly_model_path,
		anomaly_threshold=anomaly_threshold,
		mask_threshold=mask_threshold,
		min_area=min_area,
	)

	rfdetr_engine = RFDETREngine(
		model_path=rfdetr_model_path,
		threshold=rfdetr_threshold,
	)
	part_result = rfdetr_engine.detect_part(image_bgr)

	if part_result is None:
		return {
			"anomaly": anomaly_result,
			"part": None,
			"ocr": None,
		}

	crop_bgr = part_result["crop"]
	if crop_bgr.size == 0:
		raise ValueError("RF-DETR returned an empty crop.")

	ocr_engine = OCR_Engine(model_dir=ocr_model_dir)
	ocr_result = ocr_engine.predict(crop_bgr)

	return {
		"anomaly": anomaly_result,
		"part": part_result,
		"ocr": ocr_result,
	}


def _encode_image_to_base64_png(image: np.ndarray | None) -> str | None:
	if image is None or image.size == 0:
		return None

	ok, encoded = cv2.imencode(".png", image)
	if not ok:
		return None

	return base64.b64encode(encoded.tobytes()).decode("ascii")


def _extract_ocr_lines(node: Any) -> list[dict[str, Any]]:
	lines: list[dict[str, Any]] = []

	def walk(value: Any) -> None:
		if isinstance(value, dict):
			rec_texts = value.get("rec_texts")
			rec_scores = value.get("rec_scores")
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
					lines.append({"text": text, "score": score})

			if isinstance(value.get("text"), str):
				score = value.get("score")
				try:
					score = float(score) if score is not None else None
				except Exception:
					score = None
				lines.append({"text": value["text"], "score": score})

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
		deduped.append({"text": text, "score": line.get("score")})
	return deduped


def build_inspection_payload(image_path: str, combined_result: dict[str, Any]) -> dict[str, Any]:
	image_bgr = cv2.imread(image_path)
	if image_bgr is None:
		raise FileNotFoundError(f"Unable to read captured image: {image_path}")

	image_h, image_w = image_bgr.shape[:2]

	anomaly = combined_result.get("anomaly") or {}
	part = combined_result.get("part")
	ocr_raw = combined_result.get("ocr")

	anomaly_results = anomaly.get("results") or []
	anomaly_count = len(anomaly_results)
	anomaly_score = float(anomaly.get("score", 0.0) or 0.0)
	anomaly_label = int(anomaly.get("label", 0) or 0)

	mask = anomaly.get("mask")
	anomaly_map_b64 = None
	if isinstance(mask, np.ndarray) and mask.size > 0:
		if len(mask.shape) == 3:
			mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
		heatmap = cv2.applyColorMap(mask.astype(np.uint8), cv2.COLORMAP_JET)
		overlay = cv2.addWeighted(image_bgr, 0.65, heatmap, 0.35, 0)
		anomaly_map_b64 = _encode_image_to_base64_png(overlay)

	ocr_lines = _extract_ocr_lines(ocr_raw)

	total = len(ocr_lines)
	if total == 0 and anomaly_count > 0:
		total = anomaly_count
	rejected = min(total, anomaly_count) if total > 0 else anomaly_count
	accepted = max(0, total - rejected)

	wrong_text = []
	if anomaly_count > 0:
		wrong_text.append(
			{
				"text": "Anomaly region detected",
				"reason": f"score={anomaly_score:.3f}",
			}
		)

	boxes: list[dict[str, Any]] = []
	if isinstance(part, dict):
		bbox = part.get("bbox")
		if isinstance(bbox, (list, tuple)) and len(bbox) == 4 and image_w > 0 and image_h > 0:
			x1, y1, x2, y2 = [int(v) for v in bbox]
			bw = max(0, x2 - x1)
			bh = max(0, y2 - y1)
			box_label = ocr_lines[0]["text"] if ocr_lines else "Detected Part"

			boxes.append(
				{
					"id": "part-1",
					"text": box_label,
					"status": "wrong" if anomaly_count > 0 else "correct",
					"top": (y1 / image_h) * 100.0,
					"left": (x1 / image_w) * 100.0,
					"width": (bw / image_w) * 100.0,
					"height": (bh / image_h) * 100.0,
				}
			)

	return {
		"total": total,
		"accepted": accepted,
		"rejected": rejected,
		"wrongText": wrong_text,
		"boxes": boxes,
		"ocrLines": ocr_lines,
		"anomaly": {
			"label": anomaly_label,
			"score": anomaly_score,
			"count": anomaly_count,
			"mapImageBase64": anomaly_map_b64,
		},
		"capturedImagePath": image_path,
	}


def run_hardcoded_pipeline() -> dict[str, Any]:
	image_path = capture_image_from_camera(
		camera_index=CAMERA_INDEX,
		output_path=CAPTURED_IMAGE_PATH,
	)

	combined_result = run_pipeline(
		image_path=image_path,
		anomaly_model_path=ANOMALY_MODEL_PATH,
		rfdetr_model_path=RFDETR_MODEL_PATH,
		ocr_model_dir=OCR_MODEL_DIR,
		anomaly_threshold=ANOMALY_THRESHOLD,
		mask_threshold=MASK_THRESHOLD,
		min_area=MIN_AREA,
		rfdetr_threshold=RFDETR_THRESHOLD,
	)

	return build_inspection_payload(
		image_path=image_path,
		combined_result=combined_result,
	)


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok", "service": "vq-edge-python-backend"}


@app.post("/inspect/start")
def inspect_start() -> dict[str, Any]:
	try:
		return run_hardcoded_pipeline()
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/inspect/pause")
def inspect_pause() -> dict[str, str]:
	return {"status": "paused"}


@app.post("/inspect/finish")
def inspect_finish() -> dict[str, str]:
	return {"status": "finished"}


if __name__ == "__main__":
	uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=False)



