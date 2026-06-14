-- Migration 001: per-salon API keys
-- Run this in your Supabase SQL editor before deploying the updated backend.
--
-- What it does:
--   1. Adds an `api_key` column to the salons table (unique, not null after backfill).
--   2. Backfills existing salons with a random key so no row is left NULL.
--   3. Adds a unique index for fast key lookups (auth hit on every API request).

-- Step 1: Add the column as nullable first so the backfill can run.
ALTER TABLE salons
    ADD COLUMN IF NOT EXISTS api_key TEXT;

-- Step 2: Backfill existing rows with a random key.
-- gen_random_uuid() is available in all Supabase (Postgres 14+) projects.
UPDATE salons
SET api_key = replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '')
WHERE api_key IS NULL;

-- Step 3: Lock the column down — every salon must have a key going forward.
ALTER TABLE salons
    ALTER COLUMN api_key SET NOT NULL;

-- Step 4: Unique index for O(1) key lookups.
CREATE UNIQUE INDEX IF NOT EXISTS salons_api_key_idx ON salons (api_key);
