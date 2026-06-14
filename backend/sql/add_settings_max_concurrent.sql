-- Add a "chairs" / simultaneous-appointment cap to settings.
-- Run this ONCE in the Supabase SQL editor.
--
-- Why: a salon can have more stylists than chairs (e.g. 3 stylists, 2 chairs).
-- max_concurrent caps how many appointments can overlap at once across the whole
-- salon. NULL = no extra cap beyond the number of active stylists.

ALTER TABLE public.settings
  ADD COLUMN IF NOT EXISTS max_concurrent integer;
