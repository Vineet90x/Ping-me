# Ping — Architecture & Testing Guide

A plain-English map of how the backend works and exactly how to test every part.

---

## 1. What Ping does (in one breath)

Customers book salon appointments **over WhatsApp**. They text the salon's
WhatsApp number, the bot walks them through a menu (service → stylist → day →
time → confirm), and the appointment is saved. Salon owners text short commands
(`STATS`, `TOMORROW`, `UNPAID`) to check their day. There's also a normal REST
API for a future dashboard.

---

## 2. The big picture

```
   Customer / Owner (WhatsApp)
            │  text message
            ▼
        Twilio  ──────────────►  ngrok tunnel ──────►  FastAPI (main.py)  :8800
            ▲                                                 │
            │  reply (Twilio API)                             │
            └─────────────────────────────────────────────────┤
                                                              │
        ┌──────────────────────── services/ ──────────────────┴───────────┐
        │  database.py   → talks to Supabase (Postgres) over REST          │
        │  session.py    → remembers where a customer is in the menu (Redis)│
        │  booking.py    → slot math, conflict checks, create appointment   │
        │  messaging.py  → sends WhatsApp messages via Twilio               │
        │  pdf / images / storage → invoices & confirmation pictures        │
        └───────────────────────────────────────────────────────────────────┘
                                                              │
                                       Celery worker + beat (background jobs)
                                       → reminders, bulk broadcasts
```

**Three ways into the system:**
1. **WhatsApp** → `POST /api/webhooks/whatsapp` (the conversational bot).
2. **REST API** → `/api/salons/...` (for a dashboard / admin tools).
3. **Background jobs** → Celery (reminders run on a timer; broadcasts run on demand).

All three share the same `services/` helpers, so they behave identically.

---

## 3. Folder map

```
backend/
├── main.py              FastAPI app: wires routes, error handling, /health
├── config.py            Env vars, IST timezone helper, defaults
├── celery_app.py        Celery setup + schedule (reminders every 15 min)
├── tasks.py             Background jobs: send_due_reminders, send_broadcast
│
├── routes/              One file per resource = HTTP endpoints
│   ├── salons.py        register / get / update salon
│   ├── staff.py         add / list / remove stylists
│   ├── services.py      add / list / remove services
│   ├── appointments.py  create / list / get / update status / reschedule
│   ├── invoices.py      create / list / mark paid / generate PDF
│   ├── broadcasts.py    create / send / list bulk messages
│   ├── settings.py      business hours & booking rules
│   └── webhook.py       THE WhatsApp bot (conversation state machine)
│
├── models/              Pydantic models = input validation + response shapes
│   ├── salon.py  staff.py  service.py  appointment.py
│   ├── invoice.py  broadcaste.py  settings.py
│
├── services/            Shared logic (no HTTP here)
│   ├── database.py      Custom Supabase REST client (raises DBError on failure)
│   ├── session.py       Conversation memory (Redis, falls back to in-memory)
│   ├── booking.py       Slots, conflicts, get-or-create customer, create appt
│   ├── messaging.py     send_whatsapp(to, body, media) via Twilio
│   ├── pdf.py           ReportLab invoice PDF
│   ├── images.py        Pillow booking-confirmation card
│   └── storage.py       Upload files to Supabase Storage
│
├── tests/               pytest suite (no network needed)
├── seed_data.py         Python seed script (uses the live DB client)
├── seed_data.sql        SQL seed script (run in Supabase SQL editor)
└── .env                 Secrets (not committed)
```

---

## 4. The flows, step by step

### 4a. Customer booking (the heart of it)

The bot is a **state machine**. Each customer's current "step" is stored in a
session (keyed by their phone number, 30-min expiry). Each reply moves them one
step forward.

```
  Customer texts anything
          │
          ▼
   Is this number a salon OWNER?  ──yes──►  Owner commands (4b)
          │ no
          ▼
   choose_salon      (skipped automatically if only ONE salon exists)
          ▼  reply with a number
   choose_service    "1. Haircut – ₹400 (45 min) ..."
          ▼
   choose_staff      "1. Rakesh  2. Priya ..."
          ▼
   choose_date       "1. Today  2. Tomorrow  3. Wed 03 Jun ..."  (from business rules)
          ▼
   choose_time       only FREE slots, computed from hours + duration + existing bookings
          ▼
   ask_name          (only if we don't already know this customer)
          ▼
   confirm           shows a summary → customer types CONFIRM
          ▼
   ✅ Appointment saved, session cleared
```

**Special words at any time:**
- `HI` / `HELLO` / `MENU` / `BOOK` / `START` → restart the booking.
- `CANCEL` → abandon the current booking.

**What makes a slot "free":** `services/booking.py` lists every start time from
opening to closing in 30-min steps, then drops any that (a) are sooner than the
"minimum advance booking" rule, or (b) overlap an existing confirmed/completed
appointment for that stylist (using each booking's own service duration).

### 4b. Owner commands

If the texting number matches a salon's `owner_phone`, it's treated as an owner:

| Command    | Returns |
|------------|---------|
| `STATS`    | Today's counts: upcoming / completed / cancelled |
| `TOMORROW` | Tomorrow's schedule (time, service, stylist, customer) |
| `UNPAID`   | Number of unpaid invoices + total ₹ outstanding |
| anything else | The help text listing the commands |

### 4c. REST API request lifecycle

```
HTTP request → FastAPI route → Pydantic validates input (422 if bad)
   → route calls services/ helpers → database.py hits Supabase
   → success: JSON response
   → DB failure: DBError → handled globally → clean 4xx/5xx JSON
```

### 4d. Background jobs (Celery)

- **Reminders:** `tasks.send_due_reminders` runs every 15 minutes (Celery beat).
  It sends a 24-hour reminder for tomorrow's bookings and a ~1-hour reminder for
  today's upcoming ones, marking `reminder_sent_24h` / `reminder_sent_1h` so it
  never double-sends.
- **Broadcasts:** sending a broadcast fans the message out to every opted-in
  customer. The API does this in a background task; Celery has a task for it too.

---

## 5. Key design decisions (why things are the way they are)

- **Custom DB client** (`database.py`): the official Supabase SDK is flaky on
  Windows/3.12, so we use a tiny httpx wrapper. It **raises `DBError`** on real
  failures so a server problem never looks like "no rows found".
- **IST everywhere** (`config.now_ist()`): all salons are in India; times are
  stored and compared as naive IST.
- **Sessions** fall back to in-memory when Redis is down, so local testing works
  without Redis (single process only).
- **Shared `booking.py`**: both the WhatsApp bot and the REST API create
  appointments through the same code, so business rules can't drift apart.
- **Messaging is safe when unconfigured**: if Twilio creds are missing, messages
  are logged and skipped instead of crashing.

---

## 6. Data model (8 tables)

| Table | Holds | Key links |
|-------|-------|-----------|
| `salons` | salon + owner info, `owner_phone`, `upi_id` | — |
| `settings` | opening/closing time, advance-booking rules | → salon |
| `services` | name, `price` (paise), `duration_minutes`, `is_active` | → salon |
| `staff` | stylist name, phone, `is_active` | → salon |
| `customers` | phone, name, `opted_out_broadcasts` | → salon |
| `appointments` | date, time, status, reminder flags | → salon, customer, staff, service |
| `invoices` | `amount` (paise), `payment_status`, `pdf_url` | → salon, customer, appointment |
| `broadcasts` | `message_text`, `image_url`, `sent_count` | → salon |

> Money is always in **paise**: `40000` = ₹400. Soft deletes use `is_active=false`.

---

## 7. Run it locally

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

Fill in `.env` (copy from `.env.example`). **Important:** `TWILIO_ACCOUNT_SID`
must start with `AC` (from the Twilio console). Then:

```bash
# 1) API
uvicorn main:app --reload --port 8800       # http://localhost:8800/docs

# 2) Public tunnel for WhatsApp
ngrok http 8800
#   → set the https URL + /api/webhooks/whatsapp as the Twilio sandbox webhook

# 3) (optional) background jobs
celery -A celery_app.celery_app worker --loglevel=info
celery -A celery_app.celery_app beat   --loglevel=info
```

Seed demo data either way:
- **SQL:** paste `seed_data.sql` into the Supabase SQL editor, or
- **Python:** `python seed_data.py`

---

## 8. How to test — every scenario

### 8.1 Automated tests (fast, no network)

```bash
cd backend
python -m pytest tests/ -q
```

Covers: price/amount minimums, phone & UPI validation, slot generation,
double-booking prevention, customer get-or-create, phone normalisation, menu
selection, and the DB client's request plumbing. **Run this first** — green here
means the core logic is sound.

### 8.2 Smoke checks

```bash
python -c "import main; print('app OK')"     # imports cleanly
curl http://localhost:8800/health            # {"status":"ok"}
python test_db.py                             # confirms Supabase connectivity
```

### 8.3 WhatsApp — customer booking scenarios

Seed data first. Text from a number that is **NOT** an owner phone.

**Happy path**
- [ ] Send `hi` → get a welcome + service menu (or salon menu if >1 salon).
- [ ] Reply `2` → stylist menu appears.
- [ ] Reply `1` → day menu appears (Today, Tomorrow, …).
- [ ] Pick a day → only free time slots appear.
- [ ] Pick a time → asked for your name (first time only).
- [ ] Send your name → confirmation summary appears.
- [ ] Send `CONFIRM` → ✅ booked. Check the `appointments` table for the new row.

**Edge cases — type these deliberately**
- [ ] Reply with a letter (`abc`) at a menu → "Please reply with the number…".
- [ ] Reply with `0` or `99` (out of range) → same gentle re-prompt, no crash.
- [ ] Pick a fully-booked day → "No free slots that day. Pick another day."
- [ ] At confirm, type something other than `CONFIRM` → re-prompted.
- [ ] Type `CANCEL` mid-flow → booking abandoned; `HI` starts fresh.
- [ ] Type `HI` mid-flow → restarts cleanly.
- [ ] Book the **same stylist + time** from two phones → second gets
      "That slot was just taken." (conflict protection).
- [ ] Book again from the **same number** → it remembers your name (no name prompt).
- [ ] Wait 30+ min mid-flow, then reply → session expired, bot restarts politely.

**Business-rule checks**
- [ ] Today's early times don't appear if they're within the "min advance" window.
- [ ] No slots appear before opening or after closing time.
- [ ] A 90-min service near closing won't offer a slot that runs past closing.

### 8.4 WhatsApp — owner command scenarios

Text from the salon's `owner_phone` (set it in the seed to your own number).

- [ ] `STATS` → today's upcoming / completed / cancelled counts.
- [ ] `TOMORROW` → tomorrow's list (or "No appointments tomorrow").
- [ ] `UNPAID` → count + ₹ total (seed includes one unpaid invoice).
- [ ] `xyz` → help text with the three commands.

### 8.5 REST API scenarios (use Swagger at `/docs` or curl)

Replace `SID` with a real salon id.

**Salons**
```bash
curl -X POST localhost:8800/api/salons/register -H "Content-Type: application/json" \
  -d '{"owner_phone":"9999999999","owner_name":"Test","salon_name":"Test Salon","upi_id":"test@okhdfc"}'
curl localhost:8800/api/salons/by-phone/9999999999
```
- [ ] Register works; registering the same phone again → 400 "already registered".
- [ ] `owner_phone` with 5 digits → 422 validation error.

**Services / Staff**
```bash
curl -X POST localhost:8800/api/salons/SID/services -H "Content-Type: application/json" \
  -d '{"service_name":"Haircut","price":40000,"duration_minutes":45}'
curl localhost:8800/api/salons/SID/services
```
- [ ] `price: 100` (₹1) is accepted; `price: 99` → 422.
- [ ] `duration_minutes: 500` → 422 (max 480).
- [ ] Duplicate service name in same salon → 400.
- [ ] DELETE a service → it disappears from the list (soft delete).

**Appointments**
```bash
curl -X POST localhost:8800/api/salons/SID/appointments -H "Content-Type: application/json" \
  -d '{"customer_phone":"9870000009","customer_name":"Riya","service_id":"...","staff_id":"...","appointment_date":"2026-06-05","appointment_time":"14:00"}'
```
- [ ] Valid booking → 201 with the appointment.
- [ ] Past date → 422 "cannot book in the past".
- [ ] Date > 30 days out → 422.
- [ ] Time outside business hours → 400.
- [ ] Overlapping time for same staff → 400 conflict.
- [ ] `GET /appointments?date=YYYY-MM-DD` filters correctly.
- [ ] `PATCH .../{id}?status=completed` works; bad status → 400.
- [ ] `POST .../{id}/reschedule` with a free slot works; with a taken slot → 400.

**Invoices**
```bash
curl -X POST localhost:8800/api/salons/SID/invoices -H "Content-Type: application/json" \
  -d '{"customer_id":"...","amount":40000,"description":"Haircut"}'
```
- [ ] Created with a `upi_link` in the response.
- [ ] `amount: 99` → 422.
- [ ] `PATCH .../{id}?payment_status=paid` sets `paid_at`.
- [ ] `POST .../{id}/pdf` → returns a `pdf_url` (needs the storage bucket — see §9).
- [ ] `GET /invoices?status=unpaid` filters correctly.

**Broadcasts**
- [ ] Create a broadcast (`message_text` 5–500 chars; <5 → 422).
- [ ] `POST .../{id}/send` → returns recipient count, sends in the background,
      `sent_count` updates. Opted-out customers are skipped.

**Settings**
- [ ] `GET /settings` returns defaults if none set.
- [ ] `PATCH /settings` updates hours; re-fetch to confirm.

### 8.6 PDF & images
```bash
python -c "from services.pdf import generate_invoice_pdf; \
open('test.pdf','wb').write(generate_invoice_pdf({'id':'abc12345','amount':40000,'description':'Haircut','payment_status':'paid'},{'salon_name':'Neha','owner_name':'Neha','upi_id':'n@ok'},{'customer_name':'Asha','phone':'9999999999'}))"
```
- [ ] `test.pdf` opens and looks like an invoice.
- [ ] The `/invoices/{id}/pdf` endpoint returns a public URL once the Supabase
      `invoices` storage bucket exists.

### 8.7 Reminders (Celery)
- [ ] Start the worker **and** beat.
- [ ] Seed leaves a `reminder_sent_24h=false` appointment for tomorrow.
- [ ] Within 15 minutes the customer gets a reminder and the flag flips to true.
- [ ] Run it again → no duplicate reminder.

---

## 9. Troubleshooting (real issues we hit)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Twilio `401 / error 20003 invalid username` | `TWILIO_ACCOUNT_SID` not an Account SID | Use the SID starting with `AC` from the Twilio console; restart uvicorn |
| Bot replies but nothing arrives on WhatsApp | Twilio creds wrong/missing | Same as above; check server logs for `[whatsapp skipped]` |
| `Something went wrong (...)` on CONFIRM | a Python error in the flow | With `DEBUG=True` the message includes the exact error; check the terminal traceback |
| `/invoices/{id}/pdf` → 502 "upload failed" | Supabase Storage bucket missing | Create a public bucket named `invoices` (or set `SUPABASE_INVOICE_BUCKET`) |
| "Sorry, we're having a temporary issue" | `DBError` — Supabase rejected a query | Check the terminal; usually a schema/column mismatch |
| Reminders never send | Celery worker/beat not running, or Redis down | Start both; confirm `REDIS_URL` |
| `.env` change ignored | env is read once at startup | Restart uvicorn (`--reload` only watches `.py` files) |

---

## 10. One-line recap

> WhatsApp message → Twilio → FastAPI webhook → a step-by-step menu backed by
> `booking.py` (slots & rules) and `database.py` (Supabase) → appointment saved →
> reply sent back through Twilio. The REST API and Celery jobs reuse the same
> `services/` for everything else.
