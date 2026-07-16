import { CloseCircleFilled } from "@ant-design/icons";
import { Card } from "antd";
import type { WrongTextItem } from "../types/inspection";

interface WrongTextCardProps {
  items: WrongTextItem[];
  completed?: boolean;
}

export default function WrongTextCard({ items, completed = true }: WrongTextCardProps) {
  return (
    <Card
      style={{ border: "1px solid #f3b4b4", minHeight: 110, background: "#fffafa" }}
      bodyStyle={{ padding: 14 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <span style={{ fontSize: 14, fontWeight: 800, color: "var(--vq-red)" }}>
          WRONG / MISSING TEXT
        </span>
      </div>

      {items.length === 0 ? (
        completed ? (
          <div
            style={{
              border: "1px dashed #f1a2a2",
              background: "#fff4f4",
              color: "var(--vq-red)",
              fontSize: 13,
              fontWeight: 600,
              borderRadius: 12,
              padding: 14,
            }}
          >
            No issues detected
          </div>
        ) : (
          <div
            style={{
              border: "1px dashed #f1a2a2",
              background: "#fffafa",
              color: "var(--vq-text-muted)",
              fontSize: 13,
              fontWeight: 600,
              borderRadius: 12,
              padding: 14,
            }}
          >
            Waiting for inspection to complete
          </div>
        )
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {items.map((item, idx) => (
            <div
              key={`${item.text}-${idx}`}
              style={{
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                gap: 12,
                border: "1px solid #f2b5b5",
                background: "#fff4f4",
                borderRadius: 14,
                padding: "12px 14px",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10, minWidth: 0 }}>
                <CloseCircleFilled style={{ color: "var(--vq-red)", fontSize: 15, marginTop: 2 }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "var(--vq-text)", wordBreak: "break-word" }}>
                    {item.text}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 12, color: "var(--vq-red)", fontWeight: 700 }}>
                    MISSING TEXT
                  </div>
                </div>
              </div>
              <span style={{ fontSize: 12, color: "var(--vq-red)", fontWeight: 700, whiteSpace: "nowrap" }}>
                {item.reason}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
