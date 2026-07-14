import type { BoundingBox } from "../types/inspection";

interface CameraViewProps {
  boxes: BoundingBox[];
  active: boolean;
}

export default function CameraView({ boxes, active }: CameraViewProps) {
  return (
    <div
style={{
  position: "relative",
  width: "100%",
  height: "420px",
  aspectRatio: "16 / 9",
  borderRadius: 14,
  overflow: "hidden",
  background:
    "radial-gradient(circle at 30% 20%, #23303f 0%, #151c26 55%, #0e131a 100%)",
  border: "1px solid var(--vq-border)",
}} >
      {/* subtle industrial grid to suggest a camera feed, not a real image */}
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

      {!active && boxes.length === 0 && (
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

      {boxes.map((box) => {
        const color = box.status === "correct" ? "var(--vq-green)" : "var(--vq-red)";
        return (
          <div
            key={box.id}
            style={{
              position: "absolute",
              top: `${box.top}%`,
              left: `${box.left}%`,
              width: `${box.width}%`,
              height: `${box.height}%`,
              border: `2px solid ${color}`,
              borderRadius: 4,
              boxShadow: `0 0 0 9999px transparent`,
            }}
          >
            <span
              style={{
                position: "absolute",
                top: -22,
                left: -2,
                background: color,
                color: "#fff",
                fontSize: 11,
                fontWeight: 700,
                padding: "2px 6px",
                borderRadius: 4,
                whiteSpace: "nowrap",
              }}
            >
              {box.text}
            </span>
          </div>
        );
      })}

      </div>
  );
}
