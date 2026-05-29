-- ============================================================================
-- Ping — realistic demo data
-- Run in the Supabase SQL Editor (SQL → New query → paste → Run).
--
-- Behaviour:
--   * Attaches everything to your FIRST existing salon (the one the bot
--     already greets you with). If you have no salon yet, it creates one.
--   * Prices/amounts are in PAISE (100 paise = ₹1).
--   * Services & staff are guarded by name, so re-running won't duplicate them.
--   * Appointments use CURRENT_DATE so dates are always valid relative to today.
-- ============================================================================
do $$
declare
  v_salon        uuid;
  v_svc_beard    uuid;
  v_svc_haircut  uuid;
  v_svc_spa      uuid;
  v_svc_color    uuid;
  v_svc_facial   uuid;
  v_stf_rakesh   uuid;
  v_stf_priya    uuid;
  v_stf_sana     uuid;
  v_cust_asha    uuid;
  v_cust_vikram  uuid;
  v_cust_meera   uuid;
  v_appt_done    uuid;
  v_appt_today   uuid;
begin
  ---------------------------------------------------------------------------
  -- 1) Salon: use the first existing one, or create a demo salon.
  ---------------------------------------------------------------------------
  select id into v_salon from salons order by created_at nulls last limit 1;
  if v_salon is null then
    insert into salons (owner_phone, owner_name, salon_name, upi_id, plan_type, subscription_active)
    values ('9136275825', 'Neha Sharma', 'Neha''s Beauty Salon', 'neha@okhdfc', 'pro', true)
    returning id into v_salon;
  end if;

  ---------------------------------------------------------------------------
  -- 2) Settings (business hours): insert once.
  ---------------------------------------------------------------------------
  if not exists (select 1 from settings where salon_id = v_salon) then
    insert into settings (salon_id, opening_time, closing_time, days_advance_booking, min_advance_booking_minutes)
    values (v_salon, '10:00', '20:00', 30, 60);
  end if;

  ---------------------------------------------------------------------------
  -- 3) Services (price in paise).
  ---------------------------------------------------------------------------
  insert into services (salon_id, service_name, price, duration_minutes, is_active)
  select v_salon, 'Beard Trim', 15000, 20, true
  where not exists (select 1 from services where salon_id = v_salon and lower(service_name) = 'beard trim');

  insert into services (salon_id, service_name, price, duration_minutes, is_active)
  select v_salon, 'Haircut', 40000, 45, true
  where not exists (select 1 from services where salon_id = v_salon and lower(service_name) = 'haircut');

  insert into services (salon_id, service_name, price, duration_minutes, is_active)
  select v_salon, 'Hair Spa', 80000, 60, true
  where not exists (select 1 from services where salon_id = v_salon and lower(service_name) = 'hair spa');

  insert into services (salon_id, service_name, price, duration_minutes, is_active)
  select v_salon, 'Hair Color', 150000, 90, true
  where not exists (select 1 from services where salon_id = v_salon and lower(service_name) = 'hair color');

  insert into services (salon_id, service_name, price, duration_minutes, is_active)
  select v_salon, 'Facial', 60000, 40, true
  where not exists (select 1 from services where salon_id = v_salon and lower(service_name) = 'facial');

  select id into v_svc_beard   from services where salon_id = v_salon and lower(service_name) = 'beard trim'  limit 1;
  select id into v_svc_haircut from services where salon_id = v_salon and lower(service_name) = 'haircut'     limit 1;
  select id into v_svc_spa     from services where salon_id = v_salon and lower(service_name) = 'hair spa'    limit 1;
  select id into v_svc_color   from services where salon_id = v_salon and lower(service_name) = 'hair color'  limit 1;
  select id into v_svc_facial  from services where salon_id = v_salon and lower(service_name) = 'facial'      limit 1;

  ---------------------------------------------------------------------------
  -- 4) Staff.
  ---------------------------------------------------------------------------
  insert into staff (salon_id, staff_name, phone, is_active)
  select v_salon, 'Rakesh', '9820011111', true
  where not exists (select 1 from staff where salon_id = v_salon and lower(staff_name) = 'rakesh');

  insert into staff (salon_id, staff_name, phone, is_active)
  select v_salon, 'Priya', '9820022222', true
  where not exists (select 1 from staff where salon_id = v_salon and lower(staff_name) = 'priya');

  insert into staff (salon_id, staff_name, phone, is_active)
  select v_salon, 'Sana', '9820033333', true
  where not exists (select 1 from staff where salon_id = v_salon and lower(staff_name) = 'sana');

  select id into v_stf_rakesh from staff where salon_id = v_salon and lower(staff_name) = 'rakesh' limit 1;
  select id into v_stf_priya  from staff where salon_id = v_salon and lower(staff_name) = 'priya'  limit 1;
  select id into v_stf_sana   from staff where salon_id = v_salon and lower(staff_name) = 'sana'   limit 1;

  ---------------------------------------------------------------------------
  -- 5) Customers.
  ---------------------------------------------------------------------------
  insert into customers (salon_id, phone, customer_name, last_visit, last_service, opted_out_broadcasts)
  select v_salon, '9870000001', 'Asha Patil', current_date - 7, 'Haircut', false
  where not exists (select 1 from customers where salon_id = v_salon and phone = '9870000001');

  insert into customers (salon_id, phone, customer_name, last_visit, last_service, opted_out_broadcasts)
  select v_salon, '9870000002', 'Vikram Rao', current_date - 20, 'Beard Trim', false
  where not exists (select 1 from customers where salon_id = v_salon and phone = '9870000002');

  insert into customers (salon_id, phone, customer_name, last_visit, last_service, opted_out_broadcasts)
  select v_salon, '9870000003', 'Meera Joshi', null, null, false
  where not exists (select 1 from customers where salon_id = v_salon and phone = '9870000003');

  select id into v_cust_asha   from customers where salon_id = v_salon and phone = '9870000001' limit 1;
  select id into v_cust_vikram from customers where salon_id = v_salon and phone = '9870000002' limit 1;
  select id into v_cust_meera  from customers where salon_id = v_salon and phone = '9870000003' limit 1;

  ---------------------------------------------------------------------------
  -- 6) Appointments (past completed, today, and tomorrow for reminder testing).
  ---------------------------------------------------------------------------
  -- Completed visit last week
  insert into appointments (salon_id, customer_id, staff_id, service_id, appointment_date, appointment_time, status, reminder_sent_24h, reminder_sent_1h)
  values (v_salon, v_cust_asha, v_stf_rakesh, v_svc_haircut, current_date - 7, '15:00', 'completed', true, true)
  returning id into v_appt_done;

  -- Confirmed today
  insert into appointments (salon_id, customer_id, staff_id, service_id, appointment_date, appointment_time, status, reminder_sent_24h, reminder_sent_1h)
  values (v_salon, v_cust_vikram, v_stf_priya, v_svc_beard, current_date, '17:30', 'confirmed', false, false)
  returning id into v_appt_today;

  -- Confirmed tomorrow (the 24h reminder job will pick this up)
  insert into appointments (salon_id, customer_id, staff_id, service_id, appointment_date, appointment_time, status, reminder_sent_24h, reminder_sent_1h)
  values (v_salon, v_cust_meera, v_stf_sana, v_svc_spa, current_date + 1, '11:00', 'confirmed', false, false);

  ---------------------------------------------------------------------------
  -- 7) Invoices (one paid, one unpaid — so the owner UNPAID command shows data).
  ---------------------------------------------------------------------------
  insert into invoices (salon_id, customer_id, appointment_id, amount, description, payment_status, paid_at)
  values (v_salon, v_cust_asha, v_appt_done, 40000, 'Haircut', 'paid', now());

  insert into invoices (salon_id, customer_id, appointment_id, amount, description, payment_status)
  values (v_salon, v_cust_vikram, v_appt_today, 15000, 'Beard Trim', 'unpaid');

  ---------------------------------------------------------------------------
  -- 8) Broadcast (sample marketing message).
  ---------------------------------------------------------------------------
  insert into broadcasts (salon_id, message_text, image_url, sent_count)
  values (v_salon, 'Monsoon offer! 20% off all hair spa treatments this week. Reply HI to book.', null, 0);

  raise notice 'Seed complete for salon %', v_salon;
end $$;
