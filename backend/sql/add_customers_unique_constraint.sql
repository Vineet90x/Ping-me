-- Add UNIQUE (salon_id, phone) to customers, after merging any existing
-- duplicates. Run this ONCE in the Supabase SQL editor.
--
-- Why: get_or_create_customer now relies on this constraint for a race-safe
-- upsert. If two messages from the same number arrive simultaneously, the DB
-- (not the app) guarantees a single customer row.
--
-- The survivor for each (salon_id, phone) is the row with a real name
-- (not NULL / not "Customer") if one exists, otherwise the oldest row.
-- Child rows in appointments/invoices are repointed to the survivor first so
-- no foreign keys break, then the duplicates are deleted.

BEGIN;

-- Survivor map: id -> keep_id for every customer row.
CREATE TEMP TABLE _dupe_map ON COMMIT DROP AS
SELECT
  id,
  first_value(id) OVER (
    PARTITION BY salon_id, phone
    ORDER BY (customer_name IS NULL OR lower(customer_name) = 'customer'), created_at
  ) AS keep_id
FROM public.customers;

-- 1) Repoint child rows from duplicates to the survivor.
UPDATE public.appointments a
SET customer_id = m.keep_id
FROM _dupe_map m
WHERE a.customer_id = m.id AND m.id <> m.keep_id;

UPDATE public.invoices i
SET customer_id = m.keep_id
FROM _dupe_map m
WHERE i.customer_id = m.id AND m.id <> m.keep_id;

-- 2) Delete the now-orphaned duplicate customer rows.
DELETE FROM public.customers c
USING _dupe_map m
WHERE c.id = m.id AND m.id <> m.keep_id;

-- 3) Add the constraint (matches on_conflict="salon_id,phone" in the app).
ALTER TABLE public.customers
  ADD CONSTRAINT customers_salon_phone_unique UNIQUE (salon_id, phone);

COMMIT;
