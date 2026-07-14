import { Router } from "express";
import {
  startInspection,
  pauseInspection,
  resumeInspection,
  finishInspection,
  latestInspection,
} from "../controllers/inspectController";

const router = Router();

router.post("/start", startInspection);
router.post("/pause", pauseInspection);
router.post("/resume", resumeInspection);
router.post("/finish", finishInspection);
router.get("/latest", latestInspection);

export default router;
