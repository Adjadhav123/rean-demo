import type { AnomalyView, BoundingBox } from "../types/inspection";

interface CameraViewProps {
  active: boolean;
  capturedImageBase64?: string | null;
  anomaly?: AnomalyView;
  boxes?: BoundingBox[];
}

export default function CameraView({ active, capturedImageBase64, anomaly, boxes = [] }: CameraViewProps) {
  const hasImage = !!capturedImageBase64;

  return (
    <div
style={{
  position: "relative",
  width: "100%",
  height: "420px",
  aspectRatio: "16 / 9",
  borderRadius: 14,
  overflow: "hidden",
  background: hasImage
    ? "#0e131a"
    : "radial-gradient(circle at 30% 20%, #23303f 0%, #151c26 55%, #0e131a 100%)",
  border: "1px solid var(--vq-border)",
}} >
      {/* Captured crop image with annotations baked in */}
      {hasImage && (
        <img
          src={`data:image/png;base64,${capturedImageBase64}`}
          alt="Detected part crop"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "contain",
          }}
        />
      )}

      {/* OCR bounding boxes overlay */}
      {hasImage && boxes.length > 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            zIndex: 8,
            pointerEvents: "none",
          }}
        >
          {boxes.map((box) => (
            <div
              key={box.id}
              style={{
                position: "absolute",
                left: `${box.left}%`,
                top: `${box.top}%`,
                width: `${box.width}%`,
                height: `${box.height}%`,
                border: "2px solid rgba(248, 113, 113, 0.95)",
                borderRadius: 4,
                boxShadow: "0 0 0 1px rgba(15, 23, 42, 0.2) inset",
              }}
            />
          ))}
        </div>
      )}

      {/* Anomaly status badge */}
      {anomaly && hasImage && (
        <div
          style={{
            position: "absolute",
            top: 10,
            right: 10,
            background: anomaly.count > 0 ? "rgba(239,68,68,0.9)" : "rgba(34,197,94,0.9)",
            color: "#fff",
            padding: "4px 10px",
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 700,
            backdropFilter: "blur(4px)",
            zIndex: 10,
          }}
        >
          {anomaly.count > 0
            ? `⚠ ANOMALY (${anomaly.score.toFixed(3)})`
            : `✓ NORMAL (${anomaly.score.toFixed(3)})`}
        </div>
      )}

      {/* Grid placeholder when no image */}
      {!hasImage && (
        <svg
          width="100%"
          height="100%"
          style={{ position: "absolute", inset: 0, opacity: 0.25 }}
        >
          <defs>
            <pattern id="vq-grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M40 0H0V40" fill="none" stroke="#3a4a5c" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#vq-grid)" />
        </svg>
      )}

      {!active && !hasImage && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            color: "#8291a3",
            fontSize: 14,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textAlign: "center",
            padding: 16,
          }}
        >
          <div>Camera not started</div>
          <div style={{ marginTop: 8 }}>Press Start Inspection</div>
        </div>
      )}

      </div>
  );
}
