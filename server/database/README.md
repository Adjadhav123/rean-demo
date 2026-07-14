# backend/database

This folder is reserved for future backend-side database utilities
(e.g. migration runners, seed scripts) as the project grows.

The actual PostgreSQL schema used to set up the database lives in the
top-level `/database` folder of this repo:

- `/database/schema.sql` - creates the `parts` table used by this API.

The live connection pool used by all controllers is defined in
`backend/config/db.ts`.
