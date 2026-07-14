import { CloseCircleFilled } from "@ant-design/icons";
import { Card } from "antd";
import type { WrongTextItem } from "../types/inspection";

interface WrongTextCardProps {
  items: WrongTextItem[];
}

export default function WrongTextCard({ items }: WrongTextCardProps) {
  return (
    <Card
      style={{ border: "1px solid var(--vq-border)", minHeight: 110 }}
      bodyStyle={{ padding: 12 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--vq-red)" }}>
          WRONG / MISSING TEXT
        </span>
      </div>

      {items.length === 0 ? (
        <div style={{ color: "var(--vq-text-muted)", fontSize: 13 }}>No issues detected</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {items.map((item, idx) => (
            <div
              key={`${item.text}-${idx}`}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <CloseCircleFilled style={{ color: "var(--vq-red)", fontSize: 14 }} />
                <span style={{ fontSize: 15, fontWeight: 600 }}>{item.text}</span>
              </div>
              <span style={{ fontSize: 12, color: "var(--vq-red)", fontWeight: 600 }}>
                {item.reason}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
