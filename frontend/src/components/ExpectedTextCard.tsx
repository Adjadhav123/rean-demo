import { CheckCircleFilled, ClockCircleFilled, CloseCircleFilled } from "@ant-design/icons";
import { Card } from "antd";
import type { ExpectedTextMatch } from "../utils/expectedText";

interface ExpectedTextCardProps {
  items: ExpectedTextMatch[];
  live: boolean;
}

export default function ExpectedTextCard({ items, live }: ExpectedTextCardProps) {
  const matchedCount = items.filter((item) => item.status === "matched").length;
  const missingCount = items.filter((item) => item.status === "missing").length;

  return (
    <Card style={{ border: "1px solid var(--vq-border)" }} bodyStyle={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: "var(--vq-text)" }}>DEFINED TEXT MATCHING</div>
          <div style={{ marginTop: 4, fontSize: 12, color: "var(--vq-text-muted)" }}>
            Compare OCR output against the expected text list.
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--vq-green-dark)", background: "#e8f8ef", border: "1px solid #b7ebc6", borderRadius: 999, padding: "4px 10px" }}>
            {matchedCount} matched
          </span>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#b42318", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 999, padding: "4px 10px" }}>
            {missingCount} missing
          </span>
        </div>
      </div>

      {items.length === 0 ? (
        <div style={{ border: "1px dashed var(--vq-border)", borderRadius: 12, padding: 16, color: "var(--vq-text-muted)", fontSize: 13 }}>
          No expected text defined yet.
        </div>
      ) : !live ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {items.map((item) => (
            <div
              key={item.expectedText}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                borderRadius: 12,
                border: "1px solid #d7e3f4",
                background: "#f8fbff",
                padding: "10px 12px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                <ClockCircleFilled style={{ color: "var(--vq-blue)", fontSize: 15 }} />
                <span style={{ fontSize: 14, fontWeight: 600, wordBreak: "break-word" }}>{item.expectedText}</span>
              </div>
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--vq-text-muted)" }}>pending</span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {items.map((item) => {
            const matched = item.status === "matched";

            return (
              <div
                key={item.expectedText}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  borderRadius: 12,
                  border: matched ? "1px solid #b7ebc6" : "1px solid #fecaca",
                  background: matched ? "#f0fbf4" : "#fff1f1",
                  padding: "10px 12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  {matched ? (
                    <CheckCircleFilled style={{ color: "var(--vq-green)", fontSize: 15 }} />
                  ) : (
                    <CloseCircleFilled style={{ color: "var(--vq-red)", fontSize: 15 }} />
                  )}

                  <span style={{ fontSize: 14, fontWeight: 700, wordBreak: "break-word" }}>{item.expectedText}</span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
                  <span style={{ fontSize: 12, fontWeight: 800, color: matched ? "var(--vq-green-dark)" : "var(--vq-red)" }}>
                    {matched ? "matched" : "missing"}
                  </span>
                  {matched && item.detectedText ? (
                    <span style={{ fontSize: 11, color: "var(--vq-text-muted)", textAlign: "right" }}>
                      OCR: {item.detectedText}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
