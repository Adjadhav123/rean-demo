-- =========================================================
-- VisionQ OCR Inspection Demo - Database Setup
-- =========================================================
--
-- Usage:
--   1. Create the database (run from psql connected to the default
--      "postgres" database, or via createdb):
--
--        createdb visionq_ocr_demo
--
--      -- OR, from inside psql:
--        CREATE DATABASE visionq_ocr_demo;
--
--   2. Then run this script against that database to create the schema:
--
--        psql -d visionq_ocr_demo -f database/schema.sql
--
-- =========================================================

-- Stores OCR inspection configurations created on the
-- "OCR Inspection Setup" page (Page 1).
CREATE TABLE IF NOT EXISTS parts (
    id          SERIAL PRIMARY KEY,
    part_number VARCHAR(255) NOT NULL,
    model_path  TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_parts_part_number ON parts (part_number);
