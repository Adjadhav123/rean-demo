import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Button, message } from "antd";
import { CheckCircleFilled, PauseCircleFilled, PlayCircleFilled } from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";
import StatusIndicator from "../components/StatusIndicator";
import SummaryCard from "../components/SummaryCard";
import WrongTextCard from "../components/WrongTextCard";
import CameraView from "../components/CameraView";
import {
  startInspection,
  pauseInspection,
  resumeInspection,
  finishInspection,
  getLatestInspection,
} from "../services/api";
import type { InspectionResult, ScanStatus } from "../types/inspection";
import { loadExpectedTexts, matchExpectedTexts, saveExpectedTexts } from "../utils/expectedText";

const POLL_INTERVAL_MS = 1500;

type InspectionLocationState = {
  expectedTexts?: string[];
};

const EMPTY_RESULT: InspectionResult = {
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
  },
  capturedImageBase64: null,
};

export default function LiveInspectionPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ScanStatus>("idle");
  const [result, setResult] = useState<InspectionResult>(EMPTY_RESULT);
  const [cameraStatus, setCameraStatus] = useState<"ready" | "waiting" | "detecting" | "not_ready">("waiting");
  const [cameraActive, setCameraActive] = useState(false);
  const [expectedTexts, setExpectedTexts] = useState<string[]>(() => loadExpectedTexts());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const state = location.state as InspectionLocationState | null;
    if (state?.expectedTexts?.length) {
      const cleaned = state.expectedTexts.map((text) => text.trim()).filter(Boolean);
      setExpectedTexts(cleaned);
      saveExpectedTexts(cleaned);
    } else {
      setExpectedTexts(loadExpectedTexts());
    }
  }, [location.state]);

  // -----------------------------------------------------------------------
  // Polling: fetch the latest result from the backend every POLL_INTERVAL_MS
  // -----------------------------------------------------------------------
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();

    const poll = async () => {
      try {
        const data = await getLatestInspection();
        const backendStatus: string = data.status;
        const latestResult: InspectionResult | null = data.result;

        if (latestResult) {
          setResult(latestResult);
          setCameraActive(!!latestResult.capturedImageBase64);

          if (latestResult.error) {
            setCameraStatus("not_ready");
          } else {
            setCameraStatus("ready");
          }
        }

        // Sync frontend status with backend status
        if (backendStatus === "paused") {
          setStatus("paused");
          setCameraStatus("waiting");
          // Keep polling so we can show the frozen frame, but at a slower rate
        } else if (backendStatus === "finished" || backendStatus === "idle") {
          setStatus(backendStatus === "idle" ? "idle" : "finished");
          stopPolling();
        }
      } catch {
        // Silently retry on next interval (backend might be busy)
      }
    };

    // First poll immediately
    void poll();
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);
  }, [stopPolling]);

  // Clean up polling on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------
  async function handleStart() {
    if (status === "scanning") return;

    if (expectedTexts.length === 0) {
      message.error("Define at least one expected text before starting inspection.");
      navigate("/");
      return;
    }

    try {
      setStatus("scanning");
      setCameraStatus("detecting");
      setResult(EMPTY_RESULT);

      if (status === "paused") {
        // Resume from paused state
        await resumeInspection();
      } else {
        // Fresh start
        await startInspection();
      }

      // Start polling for results
      startPolling();
    } catch (err: any) {
      message.error(err?.response?.data?.error || "Failed to start inspection");
      setStatus("idle");
      setCameraStatus("not_ready");
    }
  }

  async function handlePause() {
    if (status !== "scanning") return;
    try {
      await pauseInspection();
      setStatus("paused");
      setCameraStatus("waiting");
      // Keep polling so we keep showing the latest result
    } catch (err: any) {
      message.error(err?.response?.data?.error || "Failed to pause inspection");
    }
  }

  async function handleFinish() {
    try {
      await finishInspection();
      setStatus("finished");
      setCameraStatus("not_ready");
      stopPolling();
      message.success("Inspection finished");
    } catch (err: any) {
      message.error(err?.response?.data?.error || "Failed to finish inspection");
    }
  }

  const scanBannerLabel =
    status === "scanning"
      ? "SCAN STARTED"
      : status === "paused"
        ? "SCAN PAUSED — ANOMALY DETECTED"
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

  const detectedTexts = useMemo(() => result.ocrLines.map((line) => line.text).filter(Boolean), [result.ocrLines]);
  const inspectionComplete = detectedTexts.length > 0;
  const textMatches = useMemo(
    () => matchExpectedTexts(expectedTexts, detectedTexts, inspectionComplete),
    [detectedTexts, expectedTexts, inspectionComplete],
  );

  const missingItems = useMemo(
    () =>
      textMatches
        .filter((item) => item.status === "missing")
        .map((item) => ({
          text: item.expectedText,
          reason: item.detectedText ? `Detected as ${item.detectedText}` : "Not detected in OCR",
        })),
    [textMatches],
  );

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
            gridTemplateColumns: "360px minmax(0, 1fr)",
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
              gap: 16,
              minHeight: 460,
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr",
                gap: 12,
              }}
            >
              <SummaryCard label="Total" value={result.total} color="var(--vq-text)" />
              <SummaryCard label="Accepted" value={result.accepted} color="var(--vq-green)" />
              <SummaryCard label="Rejected" value={result.rejected} color="var(--vq-red)" />
            </div>

            <WrongTextCard items={missingItems} completed={inspectionComplete} />
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
              active={cameraActive}
              capturedImageBase64={result.capturedImageBase64}
              anomaly={result.anomaly}
            />

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
                  {status === "paused" ? "Resume" : "Start"}
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
