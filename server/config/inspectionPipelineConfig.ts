export const INSPECTION_PIPELINE_CONFIG = {
  // Edit these values for your deployment.
  pythonBin: "python",
  cameraIndex: 0,
  anomalyModelPath: "C:/models/anomaly_model.ckpt",
  rfdetrModelPath: "C:/models/rfdetr_model.pth",
  ocrModelDir: undefined as string | undefined,
  anomalyThreshold: 0.5,
  maskThreshold: 128,
  minArea: 50,
  rfdetrThreshold: 0.7,
} as const;
