# VisionQ OCR Inspection - Demo Prototype

A React + Node.js + Python (FastAPI) + PostgreSQL **prototype** for an industrial OCR inspection
workflow. The Node.js Express server acts as an API gateway, proxying
inspection requests to the Python FastAPI backend which runs the ML pipeline
(anomaly detection, object detection, OCR).

Inspired by the Etavat VisionQ product family, redesigned for OCR text
inspection instead of visual feature detection.

## What's included

- **Frontend** - React + TypeScript + Vite + Ant Design, two pages:
  1. **OCR Inspection Setup** - create a part configuration (part number + AI model upload)
  2. **Live OCR Inspection** - live inspection view (summary counts, extracted/wrong text, camera view with bounding box overlays, anomaly map, OCR output)
- **Server** - Node.js + Express REST API, proxies inspection requests to the Python backend
- **Python Backend (vq-edge)** - FastAPI server running the ML pipeline (rembg, anomaly detection, RF-DETR, OCR)
- **Database** - PostgreSQL, single `parts` table
- **No authentication** - no login, users, roles, or permissions

## Architecture

```
Frontend (:5173)  →  Node.js Express (:4000)  →  Python FastAPI (:8001)
     Vite proxy            API gateway              ML pipeline
```

## Project structure

```
blank_cut/
  frontend/         React + TypeScript + Vite app
  server/           Node.js + Express API gateway
  vq-edge/          Python FastAPI ML backend
  database/         PostgreSQL schema.sql
  README.md
```

## Prerequisites

- Node.js 18+
- Python 3.10+ with dependencies installed (`cd vq-edge && pip install -r requirements.txt`)
- PostgreSQL 14+ running locally (or reachable)

## 1. Create the PostgreSQL database

```bash
createdb visionq_ocr_demo
psql -d visionq_ocr_demo -f database/schema.sql
```

(Alternatively, connect with `psql` and run `CREATE DATABASE visionq_ocr_demo;`
then run the contents of `database/schema.sql`.)

## 2. Start the Python ML backend

```bash
cd vq-edge
python main.py
```

The FastAPI server starts on **http://localhost:8001**. Health check:
`GET http://localhost:8001/health`

> **Note:** The Python backend uses hardcoded model paths (`C:/models/anomaly_model.ckpt`,
> `C:/models/rfdetr_model.pth`) and camera index `0`. Edit `vq-edge/main.py` to
> change these for your environment.

## 3. Configure and run the Node.js server

```bash
cd server
cp .env.example .env
# edit .env if your PostgreSQL credentials differ from the defaults
npm install
npm run dev
```

The API starts on **http://localhost:4000**. Health check:
`GET http://localhost:4000/api/health`

### Server environment variables (`server/.env`)

| Variable    | Default             | Description              |
|-------------|----------------------|---------------------------|
| PORT        | 4000                 | API port                  |
| PGHOST      | localhost             | PostgreSQL host           |
| PGPORT      | 5432                  | PostgreSQL port           |
| PGDATABASE  | visionq_ocr_demo      | Database name             |
| PGUSER      | postgres              | Database user             |
| PGPASSWORD  | postgres              | Database password         |

## 4. Configure and run the frontend

```bash
cd frontend
npm install
npm run dev
```

The app starts on **http://localhost:5173**.

The Vite dev server proxies `/api` and `/uploads` requests to
`http://localhost:4000` (see `frontend/vite.config.ts`), so the frontend and
backend talk to each other automatically in development - no CORS
configuration needed on your part.

If you deploy the frontend separately from the backend, set
`VITE_API_BASE_URL` in `frontend/.env` to the full backend URL
(e.g. `https://api.example.com/api`).

## API reference

| Method | Endpoint              | Description                              |
|--------|------------------------|-------------------------------------------|
| POST   | `/api/parts`            | Create a part configuration                |
| GET    | `/api/parts`             | List all part configurations               |
| GET    | `/api/parts/:id`          | Get one part configuration                 |
| PUT    | `/api/parts/:id`          | Update a part configuration                |
| DELETE | `/api/parts/:id`          | Delete a part configuration                |
| POST   | `/api/upload-model`        | Upload a `.pth` AI model file                |
| POST   | `/api/inspect/start`       | Start inspection (proxied to Python backend) |
| POST   | `/api/inspect/pause`       | Pause inspection (proxied to Python backend) |
| POST   | `/api/inspect/finish`      | Finish inspection (proxied to Python backend) |

## Connecting the frontend and backend

Nothing to configure manually in development - the Vite proxy handles it. In
production, either:

- Serve both behind the same reverse proxy (recommended, keeps `/api` relative), or
- Set `VITE_API_BASE_URL` on the frontend build to point at the backend's public URL.

