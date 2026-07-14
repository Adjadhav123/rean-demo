import express from "express";
import cors from "cors";
import path from "path";
import dotenv from "dotenv";

import inspectRoutes from "./routes/inspectRoutes";
import { errorHandler, notFoundHandler } from "./middleware/errorHandler";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve uploaded model files statically (useful for verifying uploads
// during development; not required by the frontend).
app.use("/uploads", express.static(path.join(__dirname, "uploads")));

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", service: "visionq-ocr-backend" });
});

app.use("/api/inspect", inspectRoutes);

app.use(notFoundHandler);
app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`VisionQ OCR backend running on http://localhost:${PORT}`);
});
