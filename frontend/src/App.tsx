import { Routes, Route, Navigate } from "react-router-dom";
import LiveInspectionPage from "./pages/LiveInspectionPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LiveInspectionPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
