import { Request, Response, NextFunction } from "express";
import { pool } from "../config/db";

// GET /api/parts
export async function getAllParts(_req: Request, res: Response, next: NextFunction) {
  try {
    // return all parts
    const result = await pool.query(
      "SELECT id, part_number, model_path, anomaly_model_path, created_at FROM parts ORDER BY id"
    );

    res.json(result.rows);
  } catch (err) {
    next(err);
  }
}

// GET /api/parts/:id
export async function getPartById(req: Request, res: Response, next: NextFunction) {
  try {
    const { id } = req.params;
    const result = await pool.query(
      "SELECT id, part_number, model_path, created_at FROM parts WHERE id = $1",
      [id]
    );

    if (result.rows.length === 0) {
      res.status(404).json({ error: `Part with id ${id} not found` });
      return;
    }

    res.json(result.rows[0]);
  } catch (err) {
    next(err);
  }
}

// POST /api/parts
export async function createPart(req: Request, res: Response, next: NextFunction) {
  try {
    console.log("========== CREATE PART ==========");
    console.log(req.body);

    const {
  part_number,
  model_path,
  anomaly_model_path,
} = req.body;

    console.log("part_number =", part_number);
    console.log("model_path =", model_path);

    const sql = `
INSERT INTO parts (
    part_number,
    model_path,
    anomaly_model_path
)
VALUES ($1, $2, $3)
RETURNING *;
`;

    console.log(sql);

const result = await pool.query(sql, [
  part_number,
  model_path,
  anomaly_model_path,
]);

console.log(result.rows);

res.status(201).json(result.rows[0]);

  } catch (err) {
    console.error(err);
    next(err);
  }
}
// PUT /api/parts/:id
export async function updatePart(
  req: Request,
  res: Response,
  next: NextFunction
) {
  try {
    const { id } = req.params;

    const {
      part_number,
      model_path,
      anomaly_model_path,
    } = req.body;

    const existing = await pool.query(
      "SELECT id FROM parts WHERE id = $1",
      [id]
    );

    if (existing.rows.length === 0) {
      return res.status(404).json({
        error: `Part with id ${id} not found`,
      });
    }

    const result = await pool.query(
      `
      UPDATE parts
      SET
          part_number = COALESCE($1, part_number),
          model_path = COALESCE($2, model_path),
          anomaly_model_path = COALESCE($3, anomaly_model_path)
      WHERE id = $4
      RETURNING
          id,
          part_number,
          model_path,
          anomaly_model_path,
          created_at
      `,
      [
        part_number || null,
        model_path || null,
        anomaly_model_path || null,
        id,
      ]
    );

    res.json(result.rows[0]);
  } catch (err) {
    next(err);
  }
}
// DELETE /api/parts/:id
export async function deletePart(req: Request, res: Response, next: NextFunction) {
  try {
    const { id } = req.params;
    const result = await pool.query("DELETE FROM parts WHERE id = $1 RETURNING id", [id]);

    if (result.rows.length === 0) {
      res.status(404).json({ error: `Part with id ${id} not found` });
      return;
    }

    res.status(204).send();
  } catch (err) {
    next(err);
  }
}
