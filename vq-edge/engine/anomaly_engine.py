import os 
import cv2
import asyncio 
import gc 
import torch
import tempfile 
import numpy as np

from typing import Dict

from anomalib.models import EfficientAd
from anomalib.engine import Engine 
from anomalib.data import PredictDataset 
from anomalib.pre_processing import PreProcessor
from anomalib.visualization import ImageVisualizer
from torchvision.transforms.v2 import Resize 
from rembg import remove, new_session


from device_manager import DeviceManager

ANOMALY_IMAGE_SIZE = 256

class AnomalyEngine:

    _instance = None 
    device_manager : DeviceManager
    models : Dict[str, Dict]

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance.device_manager = DeviceManager()
            instance.models = {}
            cls._instance = instance
        return cls._instance
    
    def _is_anomaly_model_ready(self, ckpt_path: str) -> bool:
        return ckpt_path in self.models
    
    def _load_anomaly_model(self, ckpt_path: str):
        """ Load and anomaly detection model from checkpoint path."""

        pre_processor = PreProcessor(transform=Resize((ANOMALY_IMAGE_SIZE, ANOMALY_IMAGE_SIZE)))

        model = EfficientAd(
            teacher_out_channels=384,
            model_size="medium",
            pre_processor=pre_processor,
            visualizer = False,
        )

        engine = Engine()

        print(f"Anomaly model loaded successfully from {ckpt_path}")
        self.models[ckpt_path] = {
            "engine" : engine,
            "model" : model,
            "ckpt_path" : ckpt_path,
        }


    def cleanup(self, model_path: str) -> bool:
        """Unload an anomaly model and clean up resources."""
        try:
            bundle = self.models.pop(model_path, None)
            if bundle and "model" in bundle:
                try:
                    model = bundle["model"]
                    if hasattr(model, "cpu"):
                        model.cpu()
                    del model
                except Exception as e:
                    print(f"Failed to move model to CPU: {e}")
                del bundle
            gc.collect()
            if self.device_manager.is_gpu():
                torch.cuda.empty_cache()
            print(f"Anomaly model {model_path} unloaded successfully")
            return True
        except Exception as e:
            print(f"Failed to unload anomaly model {model_path}: {e}")
            return False

    async def preload_anomaly_model(self, ckpt_path: str) -> bool:
        """Preload an anomaly model asynchronously so it's ready for inference."""
        try:
            if not self.is_anomaly_model_ready(ckpt_path):
                await asyncio.to_thread(self._load_anomaly_model, ckpt_path)
            return True
        except Exception as e:
            print(f"Failed to preload anomaly model {ckpt_path}: {e}")
            return False

    def _detect_anomaly(
            self,
            image_rgb: np.ndarray,
            anomaly_model_path: str,
            anomaly_threshold: float,
            mask_threshold: int,
            min_area : int,
    ) -> Dict:
        """Perfrom anomaly detection on the full image."""

        if image_rgb is None:
            print("input image is not provided.")
            return {}
        
        if not self._is_anomaly_model_ready(anomaly_model_path):
            self._load_anomaly_model(anomaly_model_path)

        anomaly_bundle = self.models.get(anomaly_model_path)

        if anomaly_bundle is None:
            raise RuntimeError(f"Anomaly model {anomaly_model_path} is not loaded.")
        
        engine = anomaly_bundle["engine"]
        model = anomaly_bundle["model"]
        ckpt_path = anomaly_bundle["ckpt_path"]

        tmp_path = None 

        try: 
            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp_file:
                tmp_path = tmp_file.name
                
                cv2.imwrite(tmp_path, cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))

                dataset = PredictDataset(path=tmp_path, transform=None)

                with torch.no_grad():
                    predictions = engine.predict(
                        model=model,
                        dataset=dataset,
                        ckpt_path=ckpt_path,
                    )

                if len(predictions) == 0:
                    return {}
                
                prediction = predictions[0]

                score = float(prediction.pred_score)
                label = int(prediction.pred_label)

                if score < anomaly_threshold:
                    return {
                        "label": label,
                        "score": score,
                        "mask" : None,
                        "results": [],
                    }
                
                anomaly_map = prediction.anomaly_map

                if isinstance(anomaly_map, torch.Tensor):
                    anomaly_map = anomaly_map.squeeze().cpu().numpy()

                anomaly_map = cv2.normalize(anomaly_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

                anomaly_map = cv2.resize(
                    anomaly_map, (image_rgb.shape[1], image_rgb.shape[0]), interpolation=cv2.INTER_LINEAR
                                )

                _, binary_mask = cv2.threshold(anomaly_map, mask_threshold, 255, cv2.THRESH_BINARY)

                kernel = np.ones((5, 5), np.uint8)

                binary_mask = cv2.morphologyEx(
                    binary_mask,
                    cv2.MORPH_OPEN,
                    kernel,
                )

                binary_mask = cv2.morphologyEx(
                    binary_mask,
                    cv2.MORPH_CLOSE,
                    kernel,
                )

                num_labels, labels_im, stats, _ = cv2.connectedComponentsWithStats(
                    binary_mask,
                    connectivity=8,
                )

                anomaly_results = []
                anomaly_id = 1

                for label in range(1, num_labels):
                    area = stats[label, cv2.CC_STAT_AREA]
                    if area < min_area:
                        continue

                    x = stats[label, cv2.CC_STAT_LEFT]
                    y = stats[label, cv2.CC_STAT_TOP]
                    w = stats[label, cv2.CC_STAT_WIDTH]
                    h = stats[label, cv2.CC_STAT_HEIGHT]

                    anomaly_results.append(
                        {
                            "id": anomaly_id,
                            "name": "anomaly",
                            "confidence": round(score, 4),
                            "bbox": [
                                x,
                                y,
                                x + w,
                                y + h,
                            ],
                            "area": float(area),
                            "mask": labels_im == label,
                        }
                    )

                    anomaly_id += 1

                print(f"Anomaly detected with score {score} and label {label}")

                return {
                    "label": label,
                    "score": score,
                    "mask": binary_mask,
                    "results": anomaly_results,
                }

        except Exception as e:
            print(f"Error while detecting anomaly: {e}")
            return {}

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)  

                
            
        

