import { useEffect, useState } from "react";
import { Button, Card, message, Tag } from "antd";
import { CheckCircleFilled, PauseCircleFilled, PlayCircleFilled } from "@ant-design/icons";
import StatusIndicator from "../components/StatusIndicator";
import SummaryCard from "../components/SummaryCard";
import WrongTextCard from "../components/WrongTextCard";
import CameraView from "../components/CameraView";
import { startInspection, pauseInspection, finishInspection } from "../services/api";
import type { InspectionResult, ScanStatus } from "../types/inspection";

export default function LiveInspectionPage() {
  const [status, setStatus] = useState<ScanStatus>("idle");
  const [result, setResult] = useState<InspectionResult>({
    total: 0,
    accepted: 0,
    rejected: 0,
    wrongText: [],
    boxes: [],
    ocrLines: [],
    anomaly: {
      label: 0,
      score: 0,
      count: 0,
      mapImageBase64: null,
    },
    capturedImageBase64: null,
  });
  const [cameraStatus, setCameraStatus] = useState<"ready" | "waiting" | "detecting" | "not_ready">("waiting");
  const [cameraActive, setCameraActive] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  async function handleStart() {
    if (status === "scanning" || isProcessing) return;

    setStatus("scanning");
    setCameraActive(false);
    setCameraStatus("detecting");
    setIsProcessing(true);

    try {
      const inspectionResult = await startInspection();
      setResult(inspectionResult);
      setCameraStatus("ready");
      setCameraActive(true);
    } catch (err: any) {
      message.error(err?.response?.data?.error || "Failed to start inspection");
      setStatus("idle");
      setCameraStatus("not_ready");
    } finally {
      setIsProcessing(false);
    }
  }

  useEffect(() => {
    void handleStart();
    // Run once on page entry so inspection starts directly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handlePause() {
    if (status !== "scanning") return;
    try {
      await pauseInspection();
      setStatus("paused");
      setCameraStatus("waiting");
    } catch (err: any) {
      message.error(err?.response?.data?.error || "Failed to pause inspection");
    }
  }

  async function handleFinish() {
    try {
      await finishInspection();
      setStatus("finished");
      setCameraStatus("not_ready");
      message.success("Inspection finished");
    } catch (err: any) {
      message.error(err?.response?.data?.error || "Failed to finish inspection");
    }
  }

  const scanBannerLabel =
    status === "scanning"
      ? "SCAN STARTED"
      : status === "paused"
      ? "SCAN PAUSED"
      : status === "finished"
      ? "SCAN FINISHED"
      : "SCAN IDLE";

  const bannerColor =
    status === "scanning"
      ? "var(--vq-green)"
      : status === "paused"
      ? "#d48806"
      : status === "finished"
      ? "#4F8EF7"
      : "#94a3b8";

  return (
    <div style={{ minHeight: "100%", background: "var(--vq-bg)" }}>
      {/* Header */}
      <div
        style={{
          background: "var(--vq-panel)",
          borderBottom: "1px solid var(--vq-border)",
          padding: "12px 24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div />

        <StatusIndicator label="Camera Status" status={cameraStatus} />
      </div>

      {/* Scan status banner */}
      <div
        style={{
          background: bannerColor,
          color: "#fff",
          textAlign: "center",
          padding: "8px 0",
          marginTop: -6,
          fontSize: 14,
          fontWeight: 800,
          letterSpacing: "0.08em",
        }}
      >
        {scanBannerLabel}
      </div>

      <div style={{ padding: "20px 24px 24px" }}>
       <div
        style={{
          display: "grid",
          gridTemplateColumns: "380px minmax(0, 1fr)",
          gap: 24,
          alignItems: "start",
        }}
      >
          {/* Left side */}
          <div
            style={{
              width: 380,
              display: "flex",
              flexDirection: "column",
              gap: 20,
              minHeight: 460,
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1.6fr",
                gap: 20,
                alignItems: "start",
              }}
            >
              <div>
                <div className="vq-eyebrow" style={{ marginBottom: 10 }}>
                  Inspection Summary
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                  }}
                >
                  <SummaryCard label="Total" value={result.total} color="var(--vq-text)" />
                  <SummaryCard label="Accepted" value={result.accepted} color="var(--vq-green)" />
                  <SummaryCard label="Rejected" value={result.rejected} color="var(--vq-red)" />
                </div>
              </div>

              <div style={{ minWidth: 0 }}>
                <WrongTextCard items={result.wrongText} />
              </div>
            </div>
          </div>

          {/* Right side */}
         <div
  style={{
    display: "flex",
    flexDirection: "column",
    height: "100%",
    width: "850px",
    marginLeft: "auto",
  }}
>
  <div className="vq-eyebrow" style={{ marginBottom: 10 }}>
    Live Camera View
  </div>

  <CameraView
    boxes={result.boxes}
    active={cameraActive}
    capturedImageBase64={result.capturedImageBase64}
  />

  <div
    style={{
      marginTop: 16,
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 16,
    }}
  >
    <Card
      title="Anomaly Map"
      bodyStyle={{ padding: 12 }}
      style={{ border: "1px solid var(--vq-border)", minHeight: 210 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <Tag color={result.anomaly.count > 0 ? "red" : "green"}>
          {result.anomaly.count > 0 ? "ANOMALY DETECTED" : "NORMAL"}
        </Tag>
        <span style={{ fontSize: 12, color: "var(--vq-text-muted)" }}>
          score: {result.anomaly.score.toFixed(3)}
        </span>
      </div>

      {result.anomaly.mapImageBase64 ? (
        <img
          src={`data:image/png;base64,${result.anomaly.mapImageBase64}`}
          alt="Anomaly map"
          style={{ width: "100%", borderRadius: 8, border: "1px solid var(--vq-border)" }}
        />
      ) : (
        <div style={{ color: "var(--vq-text-muted)", fontSize: 13 }}>
          Anomaly map not available for this inspection.
        </div>
      )}
    </Card>

    <Card
      title="OCR Output"
      bodyStyle={{ padding: 12 }}
      style={{ border: "1px solid var(--vq-border)", minHeight: 210 }}
    >
      {result.ocrLines.length === 0 ? (
        <div style={{ color: "var(--vq-text-muted)", fontSize: 13 }}>
          No OCR text detected.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {result.ocrLines.map((line, idx) => (
            <div
              key={`${line.text}-${idx}`}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                border: "1px solid var(--vq-border)",
                borderRadius: 8,
                padding: "8px 10px",
              }}
            >
              <span style={{ fontWeight: 600, fontSize: 13 }}>{line.text}</span>
              <span style={{ color: "var(--vq-text-muted)", fontSize: 12 }}>
                {line.score == null ? "score: n/a" : `score: ${line.score.toFixed(3)}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  </div>

          <div
  style={{
    marginTop: 18,
    width: "100%",
    display: "flex",
    justifyContent: "center",
  }}
>
  <div
    style={{
      display: "flex",
      gap: 16,
    }}
  >
              <Button
                size="middle"
                icon={<PauseCircleFilled />}
                disabled={status !== "scanning"}
                onClick={handlePause}
                style={{ width: 140, height: 40, fontSize: 14 }}
              >
                Pause
              </Button>

              <Button
                size="middle"
                type="primary"
                icon={<CheckCircleFilled />}
                disabled={status === "idle"}
                onClick={handleFinish}
                style={{ width: 140, height: 40, fontSize: 14 }}
              >
                Finish
              </Button>

              <Button
                size="middle"
                icon={<PlayCircleFilled />}
                onClick={handleStart}
                disabled={status === "scanning"}
                style={{
                  width: 140,
                  height: 40,
                  fontSize: 14,
                  background: "var(--vq-green)",
                  borderColor: "var(--vq-green)",
                  color: '#fff',
                }}
              >
                Start
              </Button>
            </div>
          </div>
        </div>
      </div>
      {/* End page */}
    </div>
    </div>
  );
}
