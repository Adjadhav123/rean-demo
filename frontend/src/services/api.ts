import axios from "axios";

// Relative baseURL: Vite dev server proxies /api to the Express backend
// (see vite.config.ts). In production, serve the frontend behind the same
// reverse proxy as the backend, or set VITE_API_BASE_URL.
const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

export const apiClient = axios.create({ baseURL });

export async function startInspection() {
  const res = await apiClient.post("/inspect/start");
  return res.data;
}

export async function pauseInspection() {
  const res = await apiClient.post("/inspect/pause");
  return res.data;
}

export async function finishInspection() {
  const res = await apiClient.post("/inspect/finish");
  return res.data;
}
