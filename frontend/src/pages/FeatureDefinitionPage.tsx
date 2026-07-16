import { useEffect, useMemo, useState } from "react";
import { AppstoreOutlined, DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Card, Input, message } from "antd";
import { useNavigate } from "react-router-dom";
import { loadExpectedTexts, parseExpectedTexts, saveExpectedTexts } from "../utils/expectedText";

export default function FeatureDefinitionPage() {
  const navigate = useNavigate();
  const [features, setFeatures] = useState<string[]>([]);
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    const draft = window.localStorage.getItem("vq-expected-texts-draft");
    const saved = loadExpectedTexts();
    const savedFeatures = parseExpectedTexts(saved.join("\n"));

    if (draft) {
      const draftFeatures = parseExpectedTexts(draft);
      setFeatures(draftFeatures);
      setIsSaved(
        draftFeatures.length === savedFeatures.length &&
          draftFeatures.every((value, index) => value === savedFeatures[index]),
      );
    } else {
      setFeatures(savedFeatures);
      setIsSaved(savedFeatures.length > 0);
    }
  }, []);

  useEffect(() => {
    // persist a simple draft string to preserve UX across reloads
    window.localStorage.setItem("vq-expected-texts-draft", features.join("\n"));
  }, [features]);

  const parsedTexts = useMemo(() => parseExpectedTexts(features.join("\n")), [features]);
  const validFeatureCount = useMemo(
    () => features.map((value) => value.trim()).filter(Boolean).length,
    [features],
  );
  const canStartInspection = validFeatureCount > 0 && isSaved;

  function handleStartInspection() {
    if (parsedTexts.length === 0) {
      message.error("Add at least one expected text before starting inspection.");
      return;
    }

    saveExpectedTexts(parsedTexts);
    window.localStorage.removeItem("vq-expected-texts-draft");
    navigate("/inspection", { state: { expectedTexts: parsedTexts } });
  }

  function handleSave() {
    const cleaned = parsedTexts;
    try {
      saveExpectedTexts(cleaned);
      setIsSaved(true);
      message.success("Features saved");
    } catch (error) {
      message.error("Failed to save features");
    }
  }

  function addFeature() {
    setFeatures((prev) => [...prev, ""]);
    setIsSaved(false);
  }

  function updateFeature(index: number, value: string) {
    setFeatures((prev) => prev.map((v, i) => (i === index ? value : v)));
    setIsSaved(false);
  }

  function deleteFeature(index: number) {
    setFeatures((prev) => prev.filter((_, i) => i !== index));
    setIsSaved(false);
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
            padding: "18px 24px",
            borderBottom: "1px solid var(--vq-border)",
            background: "#ffffff",
            display: "flex",
            alignItems: "center",
          }}
        >
          <div style={{ fontSize: 20, fontWeight: 800 }}>VisionQ OCR Inspection</div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 24, padding: 24 }}>
          <Card style={{ border: "1px solid #e6f0fb", borderRadius: 12, overflow: "hidden" }} bodyStyle={{ padding: 0 }}>
            <div style={{ background: "#eaf6ff", padding: 14, borderBottom: "1px solid #d7ecff" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div
                    style={{
                      width: 38,
                      height: 38,
                      borderRadius: 10,
                      background: "#2f6be8",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#fff",
                      fontSize: 18,
                    }}
                  >
                    <AppstoreOutlined />
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>Features</div>
                </div>
                <Button icon={<PlusOutlined />} onClick={addFeature} style={{ background: "#fff", border: "1px solid #cfe0ff" }}>
                  Add Feature
                </Button>
              </div>
            </div>

            <div style={{ padding: 18, background: "#fff" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {features.length === 0 ? null : features.map((value, idx) => (
                  <div key={idx} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <Input
                      value={value}
                      onChange={(e) => updateFeature(idx, e.target.value)}
                      placeholder="Enter feature name"
                      style={{ borderRadius: 8 }}
                    />
                    <Button danger icon={<DeleteOutlined />} onClick={() => deleteFeature(idx)} />
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
                <Button
                  size="large"
                  onClick={handleSave}
                  disabled={validFeatureCount === 0}
                  style={{
                    minWidth: 120,
                    background: validFeatureCount > 0 ? "#2f6be8" : undefined,
                    color: validFeatureCount > 0 ? "#fff" : undefined,
                    border: "none",
                  }}
                >
                  Save
                </Button>

                <Button
                  size="large"
                  onClick={handleStartInspection}
                  disabled={!canStartInspection}
                  style={{ minWidth: 180, background: "#14a44d", color: "#fff", border: "none" }}
                >
                  Start Inspection
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
