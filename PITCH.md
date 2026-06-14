# Ping — WhatsApp Salon Manager
### One-page brief for investors / acquirers

> A WhatsApp-native booking + payments + win-back tool for India's small neighborhood
> salons. No app for the customer to download, no software for the owner to learn — it
> all runs inside the WhatsApp they already use 8 hours a day.

---

## The problem
India has millions of small salons (2–5 chairs). They run on pen, register, and phone
calls. Two pains cost them real money every month:
- **No-shows** — a missed appointment is an empty chair and lost revenue (₹300–800 each).
- **Dormant customers** — no easy way to bring back someone who hasn't visited in weeks.

Existing tools (Tally, Vyapar, international SaaS) are too heavy, too costly, or demand an
app download and data entry the owner won't do. The owner lives on WhatsApp — so that's
where the product lives.

## The product
A single WhatsApp number serves many salons (multi-tenant, routed by the texting number):
- **Customer** texts the salon → guided booking (service → day → time → stylist), with
  automated 24h + 1h reminders to kill no-shows.
- **Owner** texts short commands: `BILL` (invoice a customer with a UPI pay-link + PDF),
  `STATS`, `TOMORROW`, `UNPAID`, and a `PAID` confirmation loop. A daily nudge flags
  invoices unpaid >24h so money doesn't slip through.
- **Win-back broadcasts** with auto-generated offer banners; customers can `STOP` to opt out.
- **Admin web dashboard** to manage every salon, booking, invoice and broadcast.

Payments are UPI-direct (no gateway, no 2% fee) — exactly how these shops already operate.

## Why it can win (and the honest risks)
**Wedge:** lead with the painkiller — *cut no-shows + refill slow days* — not self-service
booking (a phone call already does that). Reminders + win-back are the value.

**Risks an acquirer should price in:**
- Owner willingness-to-pay / churn is the real bottleneck (not the tech).
- Production WhatsApp requires Meta-approved message templates + opt-in (ban risk if ignored).
- One-shared-number-for-all-salons needs hardening under Meta's business rules.

## Unit economics (validated cost model)
- **Cost to serve a salon:** ~₹150–400/mo, driven almost entirely by WhatsApp broadcast
  volume (utility/reminder messages are ~₹0.13; service chats are free).
- **Fixed infra:** ~₹900/mo bootstrapping (free tiers) → ~₹4,000/mo at ~25 salons (Supabase
  Pro + always-on backend).
- **Price:** ₹799/mo single plan (broadcasts capped, overage billed); annual ₹7,990.
- **Break-even ≈ 8–10 paying salons. ~₹20k/mo profit at ~50 salons.**

## What exists today (this is a working product, not a deck)
- **Backend:** FastAPI + Supabase (Postgres) + Redis + Twilio + Celery. Money in paise, IST.
  WhatsApp bot, REST API, reminders, broadcasts, invoicing — all built.
- **Quality:** 38 automated tests passing; API-key guard; Twilio signature verification;
  graceful degradation (works without Redis/Twilio in dev).
- **Dashboard:** zero-build web control panel (salons, bookings, invoices, broadcasts, settings).
- **Docs:** architecture guide, manual test plan, SQL migrations, this brief.
- **Cost to run today:** ₹0 (free tiers + on-demand tunnel for live WhatsApp demos).

## Demand signal (fill in from your salon interviews)
- Salons interviewed: __ · Have the no-show pain: __ · Would pay ₹500–800/mo: __
- Memorable quotes: ____________________________________________

## What a buyer / investor gets
- A complete, tested codebase + admin dashboard, documented for handover.
- A clear go-live runbook: Meta WhatsApp Business API migration, Supabase Pro, monitoring.
- A validated cost model and pricing, and (above) early demand evidence.
- **To go live:** Meta API approval + ~₹3–12k/mo infra + the sales motion to sign salons.

---
*Repo: `Ping-me/` · Architecture: `backend/ARCHITECTURE.md` · Test plan: `backend/MANUAL_TEST_PLAN.md` · Validation kit: `SALON_VALIDATION.md`*
