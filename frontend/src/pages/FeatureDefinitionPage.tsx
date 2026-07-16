import { useEffect, useMemo, useState } from "react";
import { ArrowRightOutlined, DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Card, Input, Tag, message } from "antd";
import { useNavigate } from "react-router-dom";
import { clearExpectedTexts, parseExpectedTexts, saveExpectedTexts } from "../utils/expectedText";

const HERO_HINTS = ["Type one value per line", "Paste comma-separated text", "Continue to live inspection"]; 

export default function FeatureDefinitionPage() {
  const navigate = useNavigate();
  const [rawInput, setRawInput] = useState("");

  useEffect(() => {
    const saved = window.localStorage.getItem("vq-expected-texts-draft");
    if (saved) {
      setRawInput(saved);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("vq-expected-texts-draft", rawInput);
  }, [rawInput]);

  const parsedTexts = useMemo(() => parseExpectedTexts(rawInput), [rawInput]);

  function handleStartInspection() {
    if (parsedTexts.length === 0) {
      message.error("Add at least one expected text before starting inspection.");
      return;
    }

    saveExpectedTexts(parsedTexts);
    window.localStorage.removeItem("vq-expected-texts-draft");
    navigate("/inspection", { state: { expectedTexts: parsedTexts } });
  }

  function handleClear() {
    setRawInput("");
    clearExpectedTexts();
    window.localStorage.removeItem("vq-expected-texts-draft");
  }

  return (
    <div
      style={{
        minHeight: "100%",
        background:
          "radial-gradient(circle at top left, rgba(21,104,224,0.12) 0%, transparent 38%), radial-gradient(circle at top right, rgba(26,158,74,0.10) 0%, transparent 32%), linear-gradient(180deg, #f8fbff 0%, #f4f7fb 100%)",
        padding: 24,
      }}
    >
      <div
        style={{
          maxWidth: 1280,
          margin: "0 auto",
          border: "1px solid rgba(226,232,240,0.95)",
          borderRadius: 24,
          background: "rgba(255,255,255,0.92)",
          boxShadow: "0 18px 60px rgba(15,23,42,0.08)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            padding: "18px 24px",
            borderBottom: "1px solid var(--vq-border)",
            background: "linear-gradient(90deg, rgba(21,104,224,0.04), rgba(26,158,74,0.03))",
          }}
        >
          <div>
            <div className="vq-eyebrow">Step 1 of 2</div>
            <div style={{ fontSize: 22, fontWeight: 800, marginTop: 4 }}>Define expected text</div>
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
            {HERO_HINTS.map((hint) => (
              <Tag key={hint} color="blue" style={{ margin: 0, padding: "4px 10px", borderRadius: 999, fontWeight: 600 }}>
                {hint}
              </Tag>
            ))}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: 24, padding: 24 }}>
          <Card
            style={{ border: "1px solid var(--vq-border)", borderRadius: 20 }}
            bodyStyle={{ padding: 24 }}
          >
            <div style={{ maxWidth: 650 }}>
              <div className="vq-eyebrow">Inspection setup</div>
              <h1 style={{ margin: "10px 0 12px", fontSize: 34, lineHeight: 1.05, letterSpacing: "-0.03em" }}>
                Enter the exact text you want to validate on the part.
              </h1>
              <p style={{ margin: 0, color: "var(--vq-text-muted)", fontSize: 15, lineHeight: 1.7 }}>
                The inspection page will compare live OCR output against this list and highlight any missing text in a red box.
              </p>

              <div style={{ marginTop: 22 }}>
                <Input.TextArea
                  value={rawInput}
                  onChange={(event) => setRawInput(event.target.value)}
                  autoSize={{ minRows: 10, maxRows: 16 }}
                  placeholder={"Example:\nPROTECTOR\nUNDER\nOVER\nSET\nDIFF"}
                  style={{
                    borderRadius: 18,
                    borderColor: "var(--vq-border)",
                    background: "#fbfdff",
                    padding: 16,
                    fontSize: 15,
                    lineHeight: 1.7,
                  }}
                />
              </div>

              <div style={{ display: "flex", gap: 12, marginTop: 18, flexWrap: "wrap" }}>
                <Button
                  type="primary"
                  icon={<ArrowRightOutlined />}
                  size="large"
                  onClick={handleStartInspection}
                  disabled={parsedTexts.length === 0}
                  style={{ minWidth: 180 }}
                >
                  Continue to inspection
                </Button>

                <Button icon={<DeleteOutlined />} size="large" onClick={handleClear}>
                  Clear
                </Button>
              </div>
            </div>
          </Card>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card style={{ border: "1px solid var(--vq-border)", borderRadius: 20 }} bodyStyle={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
                <div>
                  <div className="vq-eyebrow">Preview</div>
                  <div style={{ fontSize: 16, fontWeight: 800, marginTop: 4 }}>Parsed expected text</div>
                </div>

                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--vq-blue)", background: "#edf4ff", border: "1px solid #cfe0ff", borderRadius: 999, padding: "4px 10px" }}>
                  {parsedTexts.length} items
                </span>
              </div>

              {parsedTexts.length === 0 ? (
                <div style={{ border: "1px dashed var(--vq-border)", borderRadius: 14, padding: 18, color: "var(--vq-text-muted)", fontSize: 13 }}>
                  Add the expected text on the left to see a live preview.
                </div>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                  {parsedTexts.map((text) => (
                    <Tag
                      key={text}
                      color="green"
                      style={{ margin: 0, padding: "7px 12px", borderRadius: 999, fontSize: 13, fontWeight: 700 }}
                    >
                      {text}
                    </Tag>
                  ))}
                </div>
              )}
            </Card>

            <Card style={{ border: "1px solid var(--vq-border)", borderRadius: 20 }} bodyStyle={{ padding: 20 }}>
              <div className="vq-eyebrow">Workflow</div>
              <div style={{ marginTop: 10, display: "grid", gap: 12 }}>
                {[
                  ["1", "Define the expected text list"],
                  ["2", "Open the inspection page"],
                  ["3", "Start inspection and compare OCR output"],
                ].map(([step, label]) => (
                  <div key={step} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div
                      style={{
                        width: 34,
                        height: 34,
                        borderRadius: 12,
                        background: "linear-gradient(135deg, var(--vq-blue), var(--vq-green))",
                        color: "#fff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: 800,
                        flexShrink: 0,
                      }}
                    >
                      {step}
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.5 }}>{label}</div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
