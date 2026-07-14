from __future__ import annotations

import argparse
import base64
import json
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from main import PipelineConfig, run_pipeline


def capture_image_from_camera(
    camera_index: int,
    output_path: str | Path,
    warmup_frames: int = 10,
) -> str:
    """
    Capture one frame from the selected camera and save it to disk.

    Args:
        camera_index: OpenCV camera index (0, 1, 2, ...)
        output_path: Where to save the captured image
        warmup_frames: Number of frames to discard before capture

    Returns:
        Absolute path to the saved image
    """
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

        print(f"Captured image saved: {output_path}")
        return output_path
    finally:
        cap.release()


def run_camera_pipeline(
    camera_index: int,
    anomaly_model_path: str,
    rfdetr_model_path: str,
    ocr_model_dir: str | None = None,
    output_image_path: str | None = None,
    anomaly_threshold: float = 0.5,
    mask_threshold: int = 128,
    min_area: int = 50,
    rfdetr_threshold: float = 0.7,
):
    """
    Full flow:
    1) Capture image from selected camera
    2) Remove background
    3) Run anomaly detection
    4) Run RF-DETR
    5) Run OCR on detected crop
    """
    if output_image_path is None:
        temp_dir = tempfile.gettempdir()
        output_image_path = str(Path(temp_dir) / "captured_frame.png")

    image_path = capture_image_from_camera(
        camera_index=camera_index,
        output_path=output_image_path,
    )

    config = PipelineConfig(
        image_path=image_path,
        anomaly_model_path=anomaly_model_path,
        rfdetr_model_path=rfdetr_model_path,
        ocr_model_dir=ocr_model_dir,
        anomaly_threshold=anomaly_threshold,
        mask_threshold=mask_threshold,
        min_area=min_area,
        rfdetr_threshold=rfdetr_threshold,
    )

    return run_pipeline(
        image_path=config.image_path,
        anomaly_model_path=config.anomaly_model_path,
        rfdetr_model_path=config.rfdetr_model_path,
        ocr_model_dir=config.ocr_model_dir,
        anomaly_threshold=config.anomaly_threshold,
        mask_threshold=config.mask_threshold,
        min_area=config.min_area,
        rfdetr_threshold=config.rfdetr_threshold,
    )


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
                    lines.append(
                        {
                            "text": text,
                            "score": score,
                        }
                    )

            if isinstance(value.get("text"), str):
                score = value.get("score")
                try:
                    score = float(score) if score is not None else None
                except Exception:
                    score = None
                lines.append(
                    {
                        "text": value["text"],
                        "score": score,
                    }
                )

            for child in value.values():
                walk(child)
            return

        if isinstance(value, (list, tuple)):
            for child in value:
                walk(child)
            return

        if isinstance(value, str):
            lines.append({"text": value, "score": None})

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
        deduped.append(
            {
                "text": text,
                "score": line.get("score"),
            }
        )

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture image from camera and run full inference pipeline",
    )

    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera index (default: 0)",
    )
    parser.add_argument(
        "--anomaly-model-path",
        type=str,
        required=True,
        help="Path to anomaly checkpoint",
    )
    parser.add_argument(
        "--rfdetr-model-path",
        type=str,
        required=True,
        help="Path to RF-DETR weights",
    )
    parser.add_argument(
        "--ocr-model-dir",
        type=str,
        default=None,
        help="Optional OCR model directory",
    )
    parser.add_argument(
        "--output-image-path",
        type=str,
        default=None,
        help="Optional output path for captured image",
    )
    parser.add_argument(
        "--anomaly-threshold",
        type=float,
        default=0.5,
        help="Anomaly score threshold",
    )
    parser.add_argument(
        "--mask-threshold",
        type=int,
        default=128,
        help="Binary threshold for anomaly map",
    )
    parser.add_argument(
        "--min-area",
        type=int,
        default=50,
        help="Minimum connected-component area",
    )
    parser.add_argument(
        "--rfdetr-threshold",
        type=float,
        default=0.7,
        help="RF-DETR confidence threshold",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print a single-line JSON payload for API integration",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    result = run_camera_pipeline(
        camera_index=args.camera_index,
        anomaly_model_path=args.anomaly_model_path,
        rfdetr_model_path=args.rfdetr_model_path,
        ocr_model_dir=args.ocr_model_dir,
        output_image_path=args.output_image_path,
        anomaly_threshold=args.anomaly_threshold,
        mask_threshold=args.mask_threshold,
        min_area=args.min_area,
        rfdetr_threshold=args.rfdetr_threshold,
    )

    payload = build_inspection_payload(
        image_path=args.output_image_path or str(Path(tempfile.gettempdir()) / "captured_frame.png"),
        combined_result=result,
    )

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=True))
        return

    print("Final pipeline result:")
    print(payload)


if __name__ == "__main__":
    main()
