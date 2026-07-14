import { CheckCircleFilled } from "@ant-design/icons";
import { Card } from "antd";

interface ExtractedTextCardProps {
  items: string[];
}

export default function ExtractedTextCard({ items }: ExtractedTextCardProps) {
  return (
    <Card
      style={{ border: "1px solid var(--vq-border)", height: "100%" }}
      styles={{ body: { padding: 20 } }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <CheckCircleFilled style={{ color: "var(--vq-green)", fontSize: 18 }} />
        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--vq-green-dark)" }}>
          EXTRACTED TEXT (CORRECT)
        </span>
      </div>

      {items.length === 0 ? (
        <div style={{ color: "var(--vq-text-muted)", fontSize: 13 }}>No text extracted yet</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {items.map((text, idx) => (
            <div key={`${text}-${idx}`} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <CheckCircleFilled style={{ color: "var(--vq-green)", fontSize: 14 }} />
              <span style={{ fontSize: 15, fontWeight: 600 }}>{text}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
