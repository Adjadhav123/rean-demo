import os 
import time 
from pathlib import Path 
from typing import Any

import cv2
import numpy as np 
from paddleocr import PaddleOCR 


OCR_BBOX_COLOR = (0, 255, 0)
OCR_TEXT_COLOR = (0, 0, 255)
OCR_BBOX_THICKNESS = 2


class OCR_Engine:
    """
    Singleton OCR engine using PaddleOCR with optimized configuration.
    Matches the working configuration from the first code.
    """

    _instance = None
    _initialized = False

    def __new__(
            cls,
            model_dir: str | None = None,
            lang: str = "en",
            device: str = "gpu:0",
    ):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._initialize(model_dir, lang, device)
            cls._instance = instance
            cls._initialized = True
        
        return cls._instance
    
    def _initialize(
        self, 
        model_dir: str | None, 
        lang: str,
        device: str,
    ) -> None:
        """
        Initialize PaddleOCR with the same configuration as the working first code.
        
        Key settings:
        - device: "gpu:0" for GPU inference (matches first code)
        - engine: "transformers" for better accuracy
        - Disable unnecessary document processing flags
        - Set dtype to float32 for consistency
        """

        # Handle custom model directory
        if model_dir is not None:
            model_dir = str(Path(model_dir).resolve())
            # Set the environment variable for custom model path
            os.environ["PADDLE_MODELS_PATH"] = model_dir
        
        print(f"[OCR_Engine] Initializing PaddleOCR with device={device}...")
        
        # Initialize with the same configuration as the working first code
        self.ocr = PaddleOCR(
            lang=lang,
            device=device,  # Use GPU if available
            engine="transformers",  # Better accuracy than default
            use_doc_orientation_classify=False,  # Not needed for parts
            use_doc_unwarping=False,  # Not needed for parts
            use_textline_orientation=False,  # Not needed for parts
            engine_config={
                "dtype": "float32",  # Consistent precision
            },
        )

        # Warmup with dummy image to compile CUDA kernels
        print("[OCR_Engine] Warming up with dummy image...")
        dummy = np.full((64, 256, 3), 255, dtype=np.uint8)
        try:
            self.ocr.predict(dummy)
            print("[OCR_Engine] PaddleOCR warmup completed successfully.")
        except Exception as e:
            print(f"[OCR_Engine] Warmup failed (may be device issue): {e}")

    
    def predict(self, image: np.ndarray) -> list[dict[str, Any]]:
        """
        Run OCR on the input image and return structured results.
        
        Args:
            image: Input image as BGR numpy array (from OpenCV)
            
        Returns:
            List of detected text regions with structure:
            [
                {
                    'rec_texts': [...],      # List of detected strings
                    'rec_scores': [...],     # Confidence scores (0-1)
                    'rec_boxes': [...],      # Bounding boxes (polygons or rects)
                }
            ]
        """
        if image is None or image.size == 0:
            print("[OCR_Engine] Empty image provided to predict()")
            return []
        
        try:
            results = self.ocr.predict(image)
            return results
        except Exception as e:
            print(f"[OCR_Engine] Prediction failed: {e}")
            return []


def draw_ocr_bboxes(image_bgr: np.ndarray, texts, scores, boxes):
    """
    Draw OCR bounding boxes and text on image.
    """
    annotated = image_bgr.copy()

    for idx, (text, score, box) in enumerate(zip(texts, scores, boxes)):
        box = np.array(box)

        if box.ndim == 2:
            x1 = int(box[:, 0].min())
            y1 = int(box[:, 1].min())
            x2 = int(box[:, 0].max())
            y2 = int(box[:, 1].max())
        elif box.ndim == 1 and len(box) == 4:
            x1, y1, x2, y2 = map(int, box)
        else:
            print(f"Skipping text '{text}': unknown box format {box}")
            continue

        cv2.rectangle(annotated, (x1, y1), (x2, y2), OCR_BBOX_COLOR, OCR_BBOX_THICKNESS)

        label = f"{text} ({score:.2f})"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        text_size = cv2.getTextSize(label, font, font_scale, thickness)[0]

        text_x = x1
        text_y = max(y1 - 5, text_size[1] + 5)
        cv2.rectangle(
            annotated,
            (text_x, text_y - text_size[1] - 5),
            (text_x + text_size[0], text_y + 5),
            OCR_BBOX_COLOR,
            -1,
        )

        cv2.putText(
            annotated,
            label,
            (text_x, text_y),
            font,
            font_scale,
            OCR_TEXT_COLOR,
            thickness,
        )

    return annotated


def run_ocr(crop: np.ndarray, engine: OCR_Engine | None = None) -> dict[str, Any]:
    """
    Run OCR, extract texts/scores/boxes, and return an annotated crop.
    """
    if engine is None:
        engine = OCR_Engine()

    print("\nRunning PaddleOCR...\n")
    start_time = time.time()
    result = engine.predict(crop)
    end_time = time.time()

    print(f"OCR took {(end_time - start_time) * 1000:.0f} ms.")

    if not result:
        print("No OCR result.")
        return {"texts": [], "scores": [], "boxes": [], "lines": [], "annotated": crop}

    page = result[0]

    texts = page.get("rec_texts", [])
    scores = page.get("rec_scores", [])
    boxes = page.get("rec_boxes", [])

    if len(texts) == 0:
        print("No text detected.")
        return {"texts": [], "scores": [], "boxes": [], "lines": [], "annotated": crop}

    print(f"Drawing {len(texts)} text bounding boxes...")
    annotated_crop = draw_ocr_bboxes(crop, texts, scores, boxes)

    lines: list[dict[str, Any]] = []
    for text, score, box in zip(texts, scores, boxes):
        parsed_box = _parse_bbox(box)
        lines.append(
            {
                "text": text,
                "score": float(score) if score is not None else None,
                "box": parsed_box,
            }
        )

    return {
        "texts": texts,
        "scores": scores,
        "boxes": boxes,
        "lines": lines,
        "annotated": annotated_crop,
    }


def extract_ocr_lines(
    ocr_result: list[dict[str, Any]], 
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Parse OCR results and return a list of text detections.
    
    This function extracts text, confidence scores, and bounding boxes
    from PaddleOCR output, filtering by confidence threshold.
    
    Args:
        ocr_result: Raw output from OCR_Engine.predict()
        min_confidence: Minimum confidence score to include (0.0-1.0)
        
    Returns:
        List of dicts: [{'text': str, 'score': float, 'box': [x1, y1, x2, y2]}, ...]
    """
    lines: list[dict[str, Any]] = []
    
    if not ocr_result or len(ocr_result) == 0:
        return lines
    
    # PaddleOCR returns a list; first element contains the page results
    page = ocr_result[0] if isinstance(ocr_result, list) else ocr_result
    
    if not isinstance(page, dict):
        print(f"[extract_ocr_lines] Unexpected result format: {type(page)}")
        return lines
    
    # Extract the arrays from the result
    texts = page.get("rec_texts", [])
    scores = page.get("rec_scores", [])
    boxes = page.get("rec_boxes", [])
    
    # Iterate through detected text regions
    for idx, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            continue
        
        # Get confidence score
        score = None
        if isinstance(scores, list) and idx < len(scores):
            try:
                score = float(scores[idx])
            except (ValueError, TypeError):
                score = None
        
        # Filter by confidence threshold
        if min_confidence > 0 and score is not None and score < min_confidence:
            continue
        
        # Parse bounding box
        box = None
        if isinstance(boxes, list) and idx < len(boxes):
            box = _parse_bbox(boxes[idx])
        
        lines.append({
            "text": text.strip(),
            "score": score,
            "box": box,
        })
    
    return lines


def _parse_bbox(raw_box: Any) -> list[int] | None:
    """
    Convert various bbox formats to [x1, y1, x2, y2].
    
    Handles:
    - Polygon (Nx2 array) → bounding rect
    - Rectangle (4-element array/list) → as-is
    """
    try:
        arr = np.array(raw_box)
        
        # Polygon format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        if arr.ndim == 2 and arr.shape[1] == 2:
            return [
                int(arr[:, 0].min()), int(arr[:, 1].min()),
                int(arr[:, 0].max()), int(arr[:, 1].max()),
            ]
        
        # Rectangle format: [x1, y1, x2, y2]
        if arr.ndim == 1 and len(arr) == 4:
            return list(map(int, arr))
            
    except Exception as e:
        print(f"[_parse_bbox] Failed to parse bbox: {e}")
    
    return None