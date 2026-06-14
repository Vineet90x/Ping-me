# Ping — WhatsApp Salon Booking System

## What is this?

Ping is a WhatsApp-based booking system for Indian salons. Instead of calling to book an appointment, customers just send a WhatsApp message. The bot walks them through choosing a service, date, time, and stylist — and books it. Salon owners get reminders, can create invoices, and accept UPI payments, all through the same WhatsApp number.

Built for real use. Not a demo project. The goal is to sign up actual salons in Mumbai and charge them a small monthly fee.

---

## The problem it solves

Most small salons in India:
- Take bookings over phone calls (missed calls = missed revenue)
- Write appointments in a register or memory
- Have no automated reminders (customers forget, no-shows are common)
- Chase customers manually for payment

Ping fixes all of this with zero new app for the customer — they already have WhatsApp.

---

## How it works (user's perspective)

**Customer:**
1. Sends "Hi" to the salon's WhatsApp number
2. Bot shows available services with prices
3. Customer picks service → picks a day → picks a time → picks a stylist → confirms
4. Gets a booking confirmation with a visual card
5. Gets a reminder 24 hours before and 1 hour before the appointment
6. After the service, receives an invoice with a UPI payment link (if the salon uses it)

**Salon owner (same WhatsApp number):**
- `STATS` → today's bookings count (confirmed, completed, cancelled)
- `TOMORROW` → tomorrow's full schedule
- `UNPAID` → list of outstanding invoices
- `BILL` → guided flow to create and send an invoice to a customer
- `PAID <code>` → confirm a customer's payment

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Backend API | FastAPI (Python) | Fast, modern, auto-generates API docs |
| Database | Supabase (Postgres) | Free tier, real-time capable, easy setup |
| Messaging | Twilio WhatsApp API | Handles WhatsApp send/receive reliably |
| Background Jobs | Celery + Redis | Appointment reminders run on a schedule |
| PDF Generation | ReportLab | Invoice PDFs created server-side |
| Image Generation | Pillow | Booking confirmation visual card |
| File Storage | Supabase Storage | Stores PDFs and booking images |
| Frontend Dashboard | Next.js + Tailwind + shadcn/ui | Modern, fast, free to host on Vercel |
| Payments | UPI deep links | No payment gateway needed; customer pays directly via UPI app |

---

## Architecture

```
Customer's WhatsApp
        │
        ▼
   Twilio API  ──────────────────────────────────────────────┐
        │                                                     │
        ▼                                                     │
POST /api/webhooks/whatsapp                                   │
        │                                                     │
        ▼                                                     │
  route_message()                                            sends
        │                                                  reply back
        ├── Is this the salon owner? ── owner commands
        │                                (STATS, TOMORROW, BILL…)
        │
        └── Is this a customer? ── conversation state machine
                                       (stored in Redis / memory)
                                              │
                                    choose service → date → time
                                        → stylist → confirm
                                              │
                                    booking.create_appointment()
                                              │
                                       Supabase (Postgres)
                                              │
                                    Celery sends reminders
                                    24h before + 1h before
```

The dashboard (Next.js) talks to the same FastAPI backend via REST API using a per-salon API key.

---

## Database tables

**8 tables, all linked to a `salon_id`:**

| Table | What it stores |
|---|---|
| `salons` | Salon name, owner phone, UPI ID, API key |
| `settings` | Business hours, advance booking window, chair capacity |
| `services` | Service name, price (in paise), duration in minutes |
| `staff` | Stylist names and phone numbers |
| `customers` | Customer phone, name, broadcast opt-out flag |
| `appointments` | Booking date/time, service, stylist, status, reminder flags |
| `invoices` | Amount, payment status, PDF link, UPI link |
| `broadcasts` | Message text, image URL, sent count |

Money is stored in **paise** (₹1 = 100 paise) to avoid floating point issues. All times are in IST.

---

## Features implemented

### Booking engine
- Customer books via a 5-step WhatsApp conversation
- Slot calculation respects business hours, minimum advance notice, service duration
- Double-booking prevention: checks both per-stylist conflicts and total chair capacity
- If a slot fills between listing and confirm, the customer is sent back to pick another time
- First booking asks for customer name; repeat customers skip this step

### Appointment reminders (automated)
- 24-hour reminder: runs every 15 minutes, checks tomorrow's bookings, sends once per appointment
- 1-hour reminder: runs every 15 minutes, checks appointments in the next 90 minutes
- Both are idempotent — a flag on the appointment row prevents double-sending

### Invoicing
- Owner creates invoice via WhatsApp BILL command or REST API
- Invoice PDF generated server-side (salon name, amount, paid/unpaid status)
- PDF uploaded to Supabase Storage, URL stored on the invoice
- UPI deep link generated: tapping it opens the customer's UPI app with amount pre-filled
- Customer replies PAID → owner gets a WhatsApp alert to confirm

### Broadcasts
- Owner sends a message to all opted-in customers
- Optional: provide a headline and a banner image is auto-generated
- Customers can STOP to opt out permanently
- Sent count tracked per broadcast

### Customer self-service (via WhatsApp)
- `MY BOOKING` — see upcoming confirmed appointments
- `CANCEL` — cancel the next confirmed appointment (owner is notified)
- `HELP` — see all available commands
- `STOP` / `UNSUBSCRIBE` — opt out of broadcast messages
- `PAID` — notify the salon that payment was made

### Dashboard (Next.js)
- Per-salon API key login (no password needed)
- View and manage: appointments, services, staff, invoices, broadcasts, settings
- All data fetched live from the FastAPI backend

---

## Project structure

```
Ping-me/
├── backend/
│   ├── main.py               — FastAPI app, middleware, route registration
│   ├── config.py             — Environment variables, IST timezone, defaults
│   ├── celery_app.py         — Background job schedule (reminders, nudges)
│   ├── tasks.py              — Celery task implementations
│   ├── models/               — Pydantic input/output validation models
│   ├── routes/               — HTTP endpoints (one file per feature)
│   │   ├── webhook.py        — WhatsApp bot conversation logic (~700 lines)
│   │   ├── salons.py         — Salon registration and management
│   │   ├── appointments.py   — Appointment CRUD + reschedule
│   │   ├── invoices.py       — Invoice create, list, mark paid, PDF
│   │   ├── broadcasts.py     — Broadcast create and send
│   │   ├── settings.py       — Business hours and capacity
│   │   └── pay.py            — UPI payment redirect link
│   ├── services/             — Shared business logic (no HTTP)
│   │   ├── booking.py        — Slot math, conflict checks, appointment creation
│   │   ├── database.py       — Custom Supabase REST client
│   │   ├── session.py        — Conversation state (Redis or in-memory)
│   │   ├── auth.py           — API key validation, Twilio signature check
│   │   ├── messaging.py      — Send WhatsApp messages via Twilio
│   │   ├── invoicing.py      — Invoice creation and validation
│   │   ├── payments.py       — UPI deep link builder
│   │   ├── pdf.py            — Invoice PDF generation (ReportLab)
│   │   ├── images.py         — Booking confirmation card (Pillow)
│   │   ├── banners.py        — Offer banner generation (Pillow)
│   │   └── storage.py        — File upload to Supabase Storage
│   ├── tests/                — 38+ pytest tests (run without network)
│   └── migrations/           — SQL migration scripts for Supabase
│
├── dashboard/                — Original single-page dashboard (reference)
├── PROJECT.md                — This file
├── README.md                 — Quick start
└── PITCH.md                  — One-page business summary
```

---

## API endpoints

All `/api/salons/*` routes require `X-API-Key` header (salon's API key or admin key).

| Method | Path | What it does |
|---|---|---|
| POST | `/api/salons/register` | Register a salon, returns API key |
| GET | `/api/salons/me` | Get the salon for the current API key |
| GET | `/api/salons/{id}` | Get salon by ID |
| PATCH | `/api/salons/{id}` | Update salon name / UPI ID |
| GET | `/api/salons/{id}/customers` | List customers |
| POST | `/api/salons/{id}/staff` | Add a staff member |
| GET | `/api/salons/{id}/staff` | List staff |
| DELETE | `/api/salons/{id}/staff/{staff_id}` | Deactivate staff |
| POST | `/api/salons/{id}/services` | Add a service |
| GET | `/api/salons/{id}/services` | List services |
| DELETE | `/api/salons/{id}/services/{svc_id}` | Deactivate service |
| POST | `/api/salons/{id}/appointments` | Create appointment |
| GET | `/api/salons/{id}/appointments` | List appointments (filterable by date/status) |
| PATCH | `/api/salons/{id}/appointments/{appt_id}` | Update status |
| POST | `/api/salons/{id}/appointments/{appt_id}/reschedule` | Reschedule |
| POST | `/api/salons/{id}/invoices` | Create invoice |
| GET | `/api/salons/{id}/invoices` | List invoices |
| PATCH | `/api/salons/{id}/invoices/{inv_id}` | Mark paid / update |
| GET | `/api/salons/{id}/invoices/{inv_id}/pdf` | Generate and get PDF URL |
| POST | `/api/salons/{id}/broadcasts` | Create broadcast |
| POST | `/api/salons/{id}/broadcasts/{bc_id}/send` | Send to all opted-in customers |
| GET | `/api/salons/{id}/broadcasts` | List broadcasts |
| GET | `/api/salons/{id}/settings` | Get settings |
| PATCH | `/api/salons/{id}/settings` | Update settings |
| POST | `/api/webhooks/whatsapp` | Twilio webhook (public) |
| GET | `/pay/{invoice_id}` | UPI payment redirect (public) |

Interactive docs available at `/docs` when the server is running.

---

## Running locally

```bash
# 1. Clone and set up
cd backend
pip install -r requirements.txt
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_KEY, TWILIO_*, ADMIN_API_KEY

# 2. Run the database migration
# Paste migrations/001_per_salon_api_keys.sql into Supabase SQL editor

# 3. Start the API
python main.py
# → http://localhost:8800
# → http://localhost:8800/docs  (interactive API docs)

# 4. Run tests
pytest tests/ -v

# 5. Start background jobs (optional — needed for reminders)
celery -A celery_app worker --beat --loglevel=info
```

---

## Deployment (free tier)

| Service | What runs there | Cost |
|---|---|---|
| Railway | FastAPI backend + Celery worker | Free tier (500h/month) |
| Vercel | Next.js dashboard | Free |
| Supabase | Postgres database + file storage | Free tier (500MB) |
| Upstash | Redis for sessions and Celery | Free tier (10k cmd/day) |
| Twilio | WhatsApp messaging | Pay per message (~₹0.80/message) |

---

## Business model

- **Free tier:** 1 salon, up to 50 appointments/month — used for validation
- **Starter:** ₹499/month — unlimited bookings, reminders, invoices
- **Growth:** ₹999/month — broadcasts, analytics, priority support

Target: 25 salons at ₹999/month = ₹25,000 MRR at steady state.
Cost at 25 salons: ~₹4,000/month (infra + WhatsApp). Margin: ~84%.

---

## What I built and what I learned

**What I actually built:**
- A production-grade WhatsApp chatbot with a multi-step state machine
- Real-time slot computation that handles business hours, duration, and double-booking
- Idempotent background jobs for automated reminders
- Invoice + UPI payment flow end-to-end (no payment gateway needed)
- PDF generation and cloud file storage
- Automated broadcast campaigns with opt-out handling
- A full REST API with per-salon authentication

**What I learned:**
- How to design a conversation state machine (stateless HTTP + external session store)
- Why paise is better than rupees for storing money (integer math, no float errors)
- How UPI deep links work (no Razorpay/Stripe needed for simple payments)
- How Celery beat schedules work and why idempotency flags matter
- How to build a custom DB client when the official SDK doesn't work on your platform
- How to structure a FastAPI project for a real product (not a tutorial)
