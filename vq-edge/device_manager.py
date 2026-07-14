import torch


class DeviceManager:
    def __init__(self):
        self.device = self._detect_best_device()
        self.device_type = "cuda" if self.device.type == "cuda" else "cpu"

    def _detect_best_device(self):
        if torch.cuda.is_available():
            return torch.device("cuda")
        else:
            return torch.device("cpu")
    
    def get_device(self) -> torch.device:
        return self.device
    
    def is_gpu(self) -> bool:
        return self.device_type == "cuda"
    
    