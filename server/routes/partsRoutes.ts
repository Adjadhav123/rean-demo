import { Router } from "express";
import {
  getAllParts,
  getPartById,
  createPart,
  updatePart,
  deletePart,
} from "../controllers/partsController";

const router = Router();

router.post("/", createPart);
router.get("/", getAllParts);
router.get("/:id", getPartById);
router.put("/:id", updatePart);
router.delete("/:id", deletePart);

export default router;
