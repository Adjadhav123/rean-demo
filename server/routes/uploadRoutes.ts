import { Router } from "express";
import { upload } from "../middleware/upload";
import { uploadModel } from "../controllers/uploadController";

const router = Router();

// Single .pth model file upload, field name must be "model"
router.post("/", upload.single("model"), uploadModel);

export default router;
