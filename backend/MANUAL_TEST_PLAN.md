# Ping — Manual Test Plan

Work through this top to bottom. Each scenario has **Steps**, an **Expected** result,
a checkbox, and a **Result/Notes** line — fill that in (✅ / ❌ + what happened) and
tell me; I'll fix bugs or note improvements.

Severity key for anything you find: **Critical** (blocks use / data loss) ·
**High** (feature broken) · **Medium** (wrong-but-recoverable) · **Low** (cosmetic).

---

## 0. One-time setup (do this once)

### 0.1 Install & baseline tests
```powershell
cd "C:\Users\VineetSalian\Documents\Repo\ping me\Ping-me\backend"
.\venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests/ -q
```
- [ ] **Expected:** `32 passed`. (This proves the core logic before any manual testing.)
- Result/Notes:

### 0.2 Configure `.env`
Make sure these are set (copy from `.env.example` for anything missing):
- `SUPABASE_URL`, `SUPABASE_KEY` — required
- `TWILIO_ACCOUNT_SID` (starts with `AC`), `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`
- `REDIS_URL` — optional (sessions fall back to in-memory)
- `ADMIN_API_KEY` — **set a long random string** (needed for §3)
- `PUBLIC_BASE_URL` — set to your ngrok https URL once you have it (needed for §8 pay links)
- `VERIFY_TWILIO_SIGNATURE=False` while testing locally

### 0.3 Supabase prep
- [ ] Run `sql/add_customers_unique_constraint.sql` in the Supabase SQL editor → `customers` now has `customers_salon_phone_unique`.
- [ ] **(0.3b)** Run `sql/add_settings_max_concurrent.sql` → `settings` now has a `max_concurrent` column (for the chairs cap).
- [ ] Create a **public** Storage bucket named `invoices` (Storage → New bucket → Public). Needed for invoice PDFs and booking-card images.
- Result/Notes:

### 0.4 Seed a demo salon
Edit `seed_data.py` → set `OWNER_PHONE` to **your own WhatsApp number** (10 digits, no +91), then:
```powershell
python seed_data.py
```
- [ ] **Expected:** prints "Created salon… / Updated settings / + service… / + staff…" and a Salon ID. Copy the **Salon ID** — you'll need it for REST tests.
- Result/Notes:  Salon ID = ____________________

### 0.5 Run the API + tunnel + Twilio
```powershell
# Terminal 1
uvicorn main:app --reload --port 8800
# Terminal 2
ngrok http 8800
```
- In the [Twilio Console → WhatsApp Sandbox], set **"When a message comes in"** to
  `https://<your-ngrok>.ngrok-free.app/api/webhooks/whatsapp` (POST).
- Put the ngrok https URL into `.env` as `PUBLIC_BASE_URL`, then **restart uvicorn**.
- **Join the sandbox from TWO phones:** send `join <your-sandbox-code>` to the Twilio
  sandbox number from (a) the **owner** phone (the seeded `OWNER_PHONE`) and (b) a
  **different customer** phone. Both must join or messages won't deliver.
- [ ] **Expected:** both phones get "You are all set!" from Twilio.
- Result/Notes:

### 0.6 (Optional) Background jobs for reminders (§11)
```powershell
# Terminal 3 + 4 (needs REDIS_URL)
celery -A celery_app.celery_app worker --loglevel=info
celery -A celery_app.celery_app beat   --loglevel=info
```

---

## 1. Smoke test
- [ ] **1.1** Open `http://localhost:8800/health` → `{"status":"ok"}`.
- [ ] **1.2** Open `http://localhost:8800/docs` → Swagger UI lists Salons/Staff/Services/Appointments/Invoices/Broadcasts/Settings/Webhooks/Payments.
- Result/Notes:

## 2. Logging is quiet (the "remove noisy logs" fix)
- [ ] **2.1** Watch the **uvicorn terminal**. From the customer phone send `hi`.
- **Expected:** you see roughly **one** line: `... INFO ping.webhook: WhatsApp in: <phone>: hi`.
  You should **NOT** see `httpx`/`httpcore` request spam or a `POST /api/webhooks/whatsapp 200` access line for each message.
- Result/Notes:

## 3. REST API key guard (`ADMIN_API_KEY` set)
Use `curl.exe` (not PowerShell's `curl` alias) or the Swagger "x-api-key" header field.
- [ ] **3.1 No key → 401.**
  ```powershell
  curl.exe -i http://localhost:8800/api/salons/<SALON_ID>
  ```
  **Expected:** `401 Unauthorized`, body `{"detail":"Invalid or missing API key"}`.
- [ ] **3.2 Wrong key → 401.** Add `-H "X-API-Key: wrong"` → still 401.
- [ ] **3.3 Correct key → 200.** Add `-H "X-API-Key: <your ADMIN_API_KEY>"` → returns the salon JSON.
- [ ] **3.4** `/health`, `/`, `/pay/...`, and the webhook work **without** a key.
- Result/Notes:

> For all §4 REST calls below, include `-H "X-API-Key: <key>"`.

## 4. REST CRUD (use Swagger `/docs` — easiest — or curl)
Replace `SID` with your Salon ID.

### 4.1 Salons
- [ ] Register a new salon (POST `/api/salons/register`) with a fresh phone → 200 + salon object.
- [ ] Register the **same phone again** → `400 "Phone already registered"`.
- [ ] `owner_phone` of 5 digits → `422` validation error.
- Result/Notes:

### 4.2 Services
- [ ] POST `/api/salons/SID/services` `{"service_name":"Facial","price":50000,"duration_minutes":45}` → 200.
- [ ] `price: 99` → `422` (min ₹1 = 100 paise). `duration_minutes: 500` → `422` (max 480).
- [ ] Duplicate active name → `400`. DELETE one → it disappears from GET list (soft delete).
- Result/Notes:

### 4.3 Staff
- [ ] POST `/api/salons/SID/staff` `{"staff_name":"Meena"}` → 200. GET list shows it. DELETE → gone.
- Result/Notes:

### 4.4 Appointments
- [ ] POST a valid appointment (use real service_id/staff_id, a near-future date/time in business hours) → 201.
- [ ] Past date → `422`. Date >30 days out → `422`. Time outside 10:00–20:00 → `400`.
- [ ] Overlapping time, same staff → `400` conflict.
- [ ] `GET /appointments?date=YYYY-MM-DD` filters. `PATCH .../{id}?status=completed` works; bad status → 400.
- Result/Notes:

### 4.5 Invoices (REST)
- [ ] POST `/api/salons/SID/invoices` `{"customer_id":"...","amount":40000,"description":"Haircut"}` → 200 with `upi_link` **and** `pay_url`.
- [ ] **Check:** `upi_link` shows your **salon name** in `pn=` (not "Ping").
- [ ] `amount: 99` → `422`. `PATCH .../{id}?payment_status=paid` sets `paid_at`.
- [ ] `POST .../{id}/pdf` → returns a `pdf_url` (needs the `invoices` bucket from §0.3).
- Result/Notes:

### 4.6 Settings
- [ ] `GET /settings` returns defaults (10:00/20:00/30/60) if none set. `PATCH` updates; re-GET confirms.
- Result/Notes:

## 5. WhatsApp — customer booking (from the **customer** phone)
**Happy path (new order: Service → Day → Time → Stylist)**
- [ ] `hi` → welcome + service menu (single salon) or salon menu (if >1 salon).
- [ ] reply `2` → **day** menu (Today/Tomorrow/…). reply `1`/`2` → **time** slots (free across all stylists).
- [ ] pick a time → **stylist** list showing only those free then, plus `0. Any available`.
- [ ] pick a stylist (or `0`) → asked your name (first time) → confirmation summary → `CONFIRM` → ✅ booked (+ §10 image).
- [ ] **Verify** a new row in the `appointments` table.
- [ ] **No more dead-ends:** you should never have to restart and re-pick a stylist because they were busy — busy stylists simply don't appear at that time.

**Edge cases**
- [ ] Letter `abc` at a menu → gentle "reply with the number" re-prompt (no crash).
- [ ] `0` or `99` (out of range) → same re-prompt.
- [ ] Fully-booked day → "No free slots that day. Pick another day."
- [ ] At confirm, type something other than `CONFIRM` → re-prompted.
- [ ] `CANCEL` mid-flow → abandoned; `HI` restarts.
- [ ] **At the confirm step, send `HI`** → it re-shows the CONFIRM/CANCEL prompt (does **not** restart the whole booking). *(new fix)*
- [ ] Book same stylist+time from two phones → second gets "That slot was just taken."
- [ ] Book again from same number → no name prompt (remembers you).
- Result/Notes:

**Chairs cap (run §0.3b first):** set `max_concurrent` below your stylist count via
`PATCH /api/salons/SID/settings {"max_concurrent": 2}`. With 3 stylists / 2 chairs, once 2
appointments overlap at a time, that time stops being offered and a 3rd booking is refused
("All chairs are booked"). *(new)*
- Result/Notes:

## 6. WhatsApp — owner read commands (from the **owner** phone)
- [ ] `STATS` → today's Upcoming/Completed/Cancelled counts.
- [ ] `TOMORROW` → tomorrow's list, or "No appointments tomorrow".
- [ ] `UNPAID` → count + ₹ outstanding total.
- [ ] anything else (e.g. `xyz`) → help text listing **BILL / STATS / TOMORROW / UNPAID**.
- Result/Notes:

## 7. WhatsApp — owner BILL flow (from the **owner** phone)
**Bill an existing appointment**
- [ ] First make sure there's a booking today for the customer (do §5 with today's date).
- [ ] Owner sends `BILL` → numbered list of today's customers + `0. Other`.
- [ ] reply the customer's number → "Amount for <name>? … (reply *OK* for ₹X)".
- [ ] reply `OK` (or a number like `500`) → "₹X for <name>. How was it paid? 1 UPI / 2 Cash / 3 Not paid yet".
- [ ] reply `3` (not paid) → owner gets "✅ Invoice INV-XXXX … sent to <name>. Pay link sent."
- [ ] **Customer phone receives** an invoice message: salon name, amount, a `…/pay/<id>` link, "reply PAID", and a PDF link/attachment.
- [ ] **Verify** a row in `invoices` with `payment_status=unpaid`.

**Bill a walk-in (no appointment)**
- [ ] Owner `BILL` → reply `0` → "Send the customer's 10-digit phone number."
- [ ] send a 10-digit number → "What's the amount?" → send `300` → choose `2` (Cash).
- [ ] **Expected:** invoice created `payment_status=paid`; customer (if they joined sandbox) gets a PAID invoice (no pay link).

**Edges**
- [ ] In amount step, send `lots` → "Please send a valid amount…" (stays on the step).
- [ ] Send `CANCEL` mid-BILL → "Cancelled…".
- Result/Notes:

## 8. Payment redirect `/pay/{id}` (test on a **phone**)
- [ ] From the unpaid invoice in §7, tap the `…/pay/<id>` link **on the phone**.
- **Expected:** the browser opens a UPI app chooser (GPay/PhonePe/Paytm) with the **amount pre-filled**.
- [ ] Open a `/pay/<id>` for an **already-paid** invoice → friendly "already paid" page (no redirect).
- [ ] Open `/pay/garbage` → "invalid or expired" page.
- Result/Notes: *(On desktop the `upi://` link has no handler — that's expected; test on mobile.)*

## 9. PAID confirmation loop
- [ ] With an **unpaid** invoice for the customer, the **customer** phone sends `PAID`.
- **Expected (customer):** "Thanks! We've let the salon know — they'll confirm shortly."
- **Expected (owner):** "💰 <name> says they paid ₹X for INV-XXXX. Reply *PAID XXXX* to confirm."
- [ ] Owner replies `PAID XXXX` (the code from the alert).
- **Expected (owner):** "✅ INV-XXXX marked paid (₹X)." **Expected (customer):** "✅ Payment confirmed… Thank you!"
- [ ] **Verify** the invoice flips to `paid` (also check via owner `UNPAID`).
- [ ] Customer sends `PAID` with **no** unpaid invoice → "We don't see a pending invoice…".
- [ ] Owner sends `PAID ZZZZ9999` (bad code) → "No unpaid invoice matches…".
- Result/Notes:

## 10. Booking confirmation image
- [ ] After a successful `CONFIRM` (§5), the customer receives a **confirmation card image** with the booking details (needs the `invoices` bucket).
- [ ] If the bucket is missing/misconfigured, booking still succeeds with a **text-only** confirmation (no crash).
- Result/Notes:

## 11. Broadcasts + banner + STOP (REST to create, WhatsApp to receive)
- [ ] **Create with banner:** POST `/api/salons/SID/broadcasts`
  `{"message_text":"Weekend offer! 20% off haircuts","headline":"Weekend 20% OFF","subtext":"Sat & Sun only"}`
  → response has an `image_url` pointing at a generated banner. Open it → clean banner with salon name + headline.
- [ ] `headline` of 81+ chars → `422`.
- [ ] **Send:** POST `/api/salons/SID/broadcasts/{broadcast_id}/send` → returns recipient count; opted-in customers receive the banner + text.
- [ ] **STOP:** from a customer phone send `STOP` → "You've been unsubscribed…". Re-send the broadcast → that customer is **skipped** (`sent_count` excludes them; verify in `customers.opted_out_broadcasts=true`).
- Result/Notes:

## 12. Reminders (Celery) — optional, needs worker+beat (§0.6)
- [ ] Create a `confirmed` appointment for **tomorrow** with `reminder_sent_24h=false`.
- [ ] Within ~15 min the customer gets a "tomorrow" reminder and the flag flips to `true`.
- [ ] It does **not** re-send on the next beat (idempotent).
- [ ] **Unpaid nudge:** with an invoice unpaid for >24h, the daily `notify_unpaid_invoices` task DMs the owner "X invoice(s) unpaid… send UNPAID". *(new — runs 11:00 IST; to test now, trigger it manually:* `python -c "import tasks; print(tasks.notify_unpaid_invoices())"`*)*
- Result/Notes:

## 13. Duplicate-customer prevention (the new UNIQUE + upsert)
- [ ] In Supabase, confirm the `customers_salon_phone_unique` constraint exists (§0.3).
- [ ] Book twice quickly from the **same** customer number → still **one** customer row for that salon.
- [ ] A customer with a real name who later triggers a default-name path keeps their **real name** (not reset to "Customer").
- Result/Notes:

---

## How to report back
For each ❌, tell me: the **scenario number**, what you **expected**, what **actually happened**
(copy the bot reply / API response / terminal error), and the phone/role you used. That's enough
for me to reproduce and fix. Improvement ideas welcome too — note them next to the scenario.
