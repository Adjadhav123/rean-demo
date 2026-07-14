interface SummaryCardProps {
  label: string;
  value: number;
  color: string;
}

export default function SummaryCard({ label, value, color }: SummaryCardProps) {
  return (
    <div
      style={{
        background: "var(--vq-panel)",
        border: "1px solid var(--vq-border)",
        borderRadius: 12,
        padding: "10px 12px",
        flex: 1,
        minWidth: 100,
      }}
    >
      <div className="vq-eyebrow">{label}</div>
      <div style={{ fontSize: 28, fontWeight: 800, color, marginTop: 6, lineHeight: 1 }}>
        {value}
      </div>
    </div>
  );
}
