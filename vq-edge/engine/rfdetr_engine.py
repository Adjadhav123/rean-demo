import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rfdetr import RFDETRMedium
import torch


class RFDETREngine:
    """
    Singleton RF-DETR inference engine.
    """

    _instance = None

    def __new__(
        cls,
        model_path: str,
        threshold: float = 0.7,
        device: str | None = None,
    ):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(
                model_path=model_path,
                threshold=threshold,
                device=device,
            )

        return cls._instance

    def _initialize(
        self,
        model_path: str,
        threshold: float,
        device: str | None,
    ) -> None:

        self.threshold = threshold
        self.device = device or (
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        print("Loading RF-DETR model...")

        self.model = RFDETRMedium(
            pretrain_weights=str(Path(model_path)),
            device=self.device,
        )

        print("RF-DETR loaded successfully.")

    def warmup(self) -> None:
        """Runs one dummy inference."""

        print("Warming up RF-DETR...")

        dummy = Image.new(
            "RGB",
            (256, 256),
            color=(255, 255, 255),
        )

        self.model.predict(
            dummy,
            threshold=self.threshold,
        )

        print("RF-DETR warmup complete.")


    def predict(self, image_bgr: np.ndarray):
        """
        Run RF-DETR inference.

        Returns the raw detections object.
        """

        image_rgb = cv2.cvtColor(
            image_bgr,
            cv2.COLOR_BGR2RGB,
        )

        image = Image.fromarray(image_rgb)

        start = time.perf_counter()

        detections = self.model.predict(
            image,
            threshold=self.threshold,
        )

        elapsed = (time.perf_counter() - start) * 1000

        print(f"RF-DETR inference: {elapsed:.2f} ms")

        return detections


    def detect_part(self, image_bgr: np.ndarray):
        """
        Detect the highest-confidence object.

        Returns
        -------
        dict | None
        """

        detections = self.predict(image_bgr)

        if len(detections.xyxy) == 0:
            print("No object detected.")
            return None

        idx = np.argmax(detections.confidence)

        x1, y1, x2, y2 = (
            detections.xyxy[idx]
            .astype(int)
            .tolist()
        )

        h, w = image_bgr.shape[:2]

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        crop = image_bgr[y1:y2, x1:x2]

        confidence = float(detections.confidence[idx])

        class_id = None
        if hasattr(detections, "class_id"):
            class_id = int(detections.class_id[idx])

        print(
            f"Detected Part: ({x1}, {y1}) -> ({x2}, {y2})"
        )
        print(f"Confidence: {confidence:.3f}")

        return {
            "crop": crop,
            "bbox": (x1, y1, x2, y2),
            "confidence": confidence,
            "class_id": class_id,
            "detections": detections,
        } 