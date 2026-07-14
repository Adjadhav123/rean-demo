import os 
import time 
from pathlib import Path 

import numpy as np 
from paddleocr import PaddleOCR 

class OCR_Engine:

    _instance = None

    def __new__(
            cls,
            model_dir: str | None = None,
            lang: str = "en",
    ):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(model_dir, lang)
        
        return cls._instance
    
    def _initialize(self, model_dir: str | None, lang: str) -> None:

        if model_dir is not None:
            model_dir = str(Path(model_dir).resolve())

            os.environ["PADDLE_PDX_MODEL_SOURCE"] = model_dir 
        
        self.ocr = PaddleOCR(
            device="gpu:0",
            engine="transformers",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine_config={
                "dtype": "float32",
            },
        )

        dummy = np.full((64, 256, 3), 255, dtype=np.uint8)

        self.ocr.predict(dummy)

        print("PaddleOCR preloaded.")

    
    def predict(self, image: np.ndarray):

        results = self.ocr.predict(image)

        return results



