import { Pool } from "pg";

export const pool = new Pool({
  host: "localhost",
  port: 5432,
  user: "postgres",
  password: "mysecret",
  database: "visionq_ocr_demo",

  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,

  keepAlive: true,
});

export async function testConnection() {
  try {
    const client = await pool.connect();

    console.log("✅ Connected to PostgreSQL");

    const db = await client.query(
      "SELECT current_database(), current_user"
    );

    console.log(db.rows);

    const tables = await client.query(`
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema='public';
    `);

    console.log("Tables:", tables.rows);

    client.release();
  } catch (err) {
    console.error(err);
  }
}

pool.on("error", (err) => {
  console.error("Unexpected PostgreSQL error:", err);
});