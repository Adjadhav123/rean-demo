import { Request, Response, NextFunction } from "express";

// POST /api/upload-model
// Accepts a single .pth model file (multer middleware handles validation
// and disk storage). Returns the relative path so the frontend can store
// it against a part configuration via POST/PUT /api/parts.
export async function uploadModel(req: Request, res: Response, next: NextFunction) {
  try {
    if (!req.file) {
      res.status(400).json({ error: "No model file uploaded (expected field 'model')" });
      return;
    }

    const modelPath = `uploads/${req.file.filename}`;

    res.status(201).json({
      message: "Model uploaded successfully",
      model_path: modelPath,
      original_name: req.file.originalname,
      size_bytes: req.file.size,
    });
  } catch (err) {
    next(err);
  }
}
