import multer from "multer";
import path from "path";
import fs from "fs";
import { Request } from "express";

const UPLOAD_DIR = path.join(__dirname, "..", "uploads");

// Ensure the uploads directory exists (created lazily on first boot).
if (!fs.existsSync(UPLOAD_DIR)) {
  fs.mkdirSync(UPLOAD_DIR, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => {
    cb(null, UPLOAD_DIR);
  },
  filename: (_req, file, cb) => {
    const timestamp = Date.now();
    const safeOriginalName = file.originalname.replace(/[^a-zA-Z0-9._-]/g, "_");
    cb(null, `${timestamp}-${safeOriginalName}`);
  },
});

// Accept both .pth (OCR Model) and .ckpt (Anomaly Model).
// text detection and OCR recognition - there is intentionally no separate
// "detection model" vs "OCR model" concept in this prototype.
function fileFilter(
  _req: Request,
  file: Express.Multer.File,
  cb: multer.FileFilterCallback
) {
  const ext = path.extname(file.originalname).toLowerCase();

  if (ext !== ".pth" && ext !== ".ckpt") {
    cb(new Error("Only .pth and .ckpt model files are allowed"));
    return;
  }

  cb(null, true);
}

export const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: 1024 * 1024 * 1024 }, // 1GB, model files can be large
});

export const UPLOADS_DIR = UPLOAD_DIR;
