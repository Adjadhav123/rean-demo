import { Routes, Route, Navigate } from "react-router-dom";
import FeatureDefinitionPage from "./pages/FeatureDefinitionPage";
import LiveInspectionPage from "./pages/LiveInspectionPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<FeatureDefinitionPage />} />
      <Route path="/inspection" element={<LiveInspectionPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
