import { Request, Response, NextFunction } from "express";
import http from "node:http";

const PYTHON_BACKEND_HOST = "127.0.0.1";
const PYTHON_BACKEND_PORT = 8001;

async function postToPythonBackend(pathname: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        host: PYTHON_BACKEND_HOST,
        port: PYTHON_BACKEND_PORT,
        path: pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      },
      (resp) => {
        let body = "";

        resp.on("data", (chunk: Buffer) => {
          body += chunk.toString("utf8");
        });

        resp.on("end", () => {
          try {
            const parsed = body ? (JSON.parse(body) as Record<string, unknown>) : {};

            if ((resp.statusCode ?? 500) >= 400) {
              reject(new Error(`Python backend error ${resp.statusCode}: ${body}`));
              return;
            }

            resolve(parsed);
          } catch (err) {
            reject(
              new Error(
                `Failed to parse Python backend response from ${pathname}: ${String(err)}`,
              ),
            );
          }
        });
      },
    );

    req.on("error", (err) => {
      reject(
        new Error(
          `Unable to connect to Python backend at ${PYTHON_BACKEND_HOST}:${PYTHON_BACKEND_PORT}. ${String(err)}`,
        ),
      );
    });

    req.write("{}");
    req.end();
  });
}

export async function startInspection(req: Request, res: Response, next: NextFunction) {
  try {
    const result = await postToPythonBackend("/inspect/start");
    res.status(200).json(result);
  } catch (err) {
    next(err);
  }
}

export async function pauseInspection(req: Request, res: Response, next: NextFunction) {
  try {
    const result = await postToPythonBackend("/inspect/pause");
    res.status(200).json(result);
  } catch (err) {
    next(err);
  }
}

export async function finishInspection(req: Request, res: Response, next: NextFunction) {
  try {
    const result = await postToPythonBackend("/inspect/finish");
    res.status(200).json(result);
  } catch (err) {
    next(err);
  }
}
