export interface WrongTextItem {
  text: string;
  reason: string;
}

export interface OcrLine {
  text: string;
  score: number | null;
}

export interface ExpectedTextMatch {
  expectedText: string;
  status: "matched" | "missing" | "pending";
  detectedText?: string | null;
}

export interface AnomalyView {
  label: number;
  score: number;
  count: number;
}

export interface BoundingBox {
  id: string;
  text: string;
  status: "correct" | "wrong";
  // Percentage-based coordinates (0-100) relative to the camera view,
  // so overlays scale with the image regardless of rendered size.
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface InspectionResult {
  total: number;
  accepted: number;
  rejected: number;
  frameNumber?: number;

  // This comes from the backend but will NOT be displayed in the UI.
  correctText?: string[];

  // This will be displayed in the UI.
  wrongText: WrongTextItem[];

  // Bounding boxes received from Python.
  boxes: BoundingBox[];

  ocrLines: OcrLine[];
  anomaly: AnomalyView;
  capturedImageBase64?: string | null;
  error?: string;
}

export type ScanStatus = "idle" | "scanning" | "paused" | "finished";
