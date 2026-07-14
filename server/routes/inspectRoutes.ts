import { Router } from "express";
import {
  startInspection,
  pauseInspection,
  finishInspection,
} from "../controllers/inspectController";

const router = Router();

router.post("/start", startInspection);
router.post("/pause", pauseInspection);
router.post("/finish", finishInspection);

export default router;
