import { NextFunction, Request, Response } from "express";

// Simple centralized error handler. Keeps controllers free of
// try/catch boilerplate for unexpected failures - controllers call
// next(err) and this middleware formats the response.
export function errorHandler(
  err: any,
  _req: Request,
  res: Response,
  _next: NextFunction
) {
  console.error("API Error:", err);

  const status = err.status || 500;
  const message = err.message || "Internal server error";

  res.status(status).json({
    error: message,
  });
}

export function notFoundHandler(req: Request, res: Response) {
  res.status(404).json({ error: `Route not found: ${req.method} ${req.originalUrl}` });
}
