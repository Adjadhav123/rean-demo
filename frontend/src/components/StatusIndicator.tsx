interface StatusIndicatorProps {
  label: string;
  status: "ready" | "waiting" | "detecting" | "not_ready";
}

export default function StatusIndicator({
  label,
  status,
}: StatusIndicatorProps) {
  const ready = status === "ready";
  const notReady = status === "not_ready";
  const detecting = status === "detecting";

  const dotColor = ready ? "#22c55e" : notReady ? "#ef4444" : detecting ? "#f59e0b" : "#f59e0b";
  const labelText = ready ? "Ready" : notReady ? "Not Ready" : detecting ? "Detecting" : "Waiting";

  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #d9d9d9",
        borderRadius: 8,
        padding: "8px 12px",
        minWidth: 140,
        boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: "#6b7280",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        {label}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginTop: 5,
        }}
      >
        <div
          style={{
            width: 9,
            height: 9,
            borderRadius: "50%",
            background: dotColor,
          }}
        />

        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {labelText}
        </span>
      </div>
    </div>
  );
}