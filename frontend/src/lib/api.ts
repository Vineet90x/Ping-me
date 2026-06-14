// Use relative paths so Next.js rewrites proxy to the backend (no CORS issues).
// next.config.ts maps /api/* → NEXT_PUBLIC_API_URL/api/* on both dev and Vercel.
const API_BASE = "";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  apiKey: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...(options.headers || {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new ApiError(body.detail || `Request failed`, res.status);
  }

  if (res.status === 204) return null as T;
  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export function getMySalon(apiKey: string) {
  return request<Salon>("/api/salons/me", apiKey);
}

// ── Appointments ─────────────────────────────────────────────────────────────

export function getAppointments(salonId: string, apiKey: string, params?: Record<string, string>) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<Appointment[]>(`/api/salons/${salonId}/appointments${qs}`, apiKey);
}

export function updateAppointment(
  salonId: string,
  appointmentId: string,
  data: { status: string },
  apiKey: string
) {
  return request(`/api/salons/${salonId}/appointments/${appointmentId}`, apiKey, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function rescheduleAppointment(
  salonId: string,
  appointmentId: string,
  data: { appointment_date: string; appointment_time: string },
  apiKey: string
) {
  return request(`/api/salons/${salonId}/appointments/${appointmentId}/reschedule`, apiKey, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Services ─────────────────────────────────────────────────────────────────

export function getServices(salonId: string, apiKey: string) {
  return request<Service[]>(`/api/salons/${salonId}/services`, apiKey);
}

export function createService(salonId: string, data: ServiceCreate, apiKey: string) {
  return request<Service>(`/api/salons/${salonId}/services`, apiKey, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateService(salonId: string, serviceId: string, data: { service_name?: string; price?: number; duration_minutes?: number }, apiKey: string) {
  return request<Service>(`/api/salons/${salonId}/services/${serviceId}`, apiKey, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteService(salonId: string, serviceId: string, apiKey: string) {
  return request(`/api/salons/${salonId}/services/${serviceId}`, apiKey, { method: "DELETE" });
}

// ── Staff ─────────────────────────────────────────────────────────────────────

export function getStaff(salonId: string, apiKey: string) {
  return request<Staff[]>(`/api/salons/${salonId}/staff`, apiKey);
}

export function createStaff(salonId: string, data: StaffCreate, apiKey: string) {
  return request<Staff>(`/api/salons/${salonId}/staff`, apiKey, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateStaff(salonId: string, staffId: string, data: { staff_name?: string; phone?: string }, apiKey: string) {
  return request<Staff>(`/api/salons/${salonId}/staff/${staffId}`, apiKey, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteStaff(salonId: string, staffId: string, apiKey: string) {
  return request(`/api/salons/${salonId}/staff/${staffId}`, apiKey, { method: "DELETE" });
}

// ── Invoices ─────────────────────────────────────────────────────────────────

export function getInvoices(salonId: string, apiKey: string, params?: Record<string, string>) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<Invoice[]>(`/api/salons/${salonId}/invoices${qs}`, apiKey);
}

export function createInvoice(salonId: string, data: InvoiceCreate, apiKey: string) {
  return request<Invoice>(`/api/salons/${salonId}/invoices`, apiKey, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function markInvoicePaid(salonId: string, invoiceId: string, apiKey: string) {
  return request(`/api/salons/${salonId}/invoices/${invoiceId}`, apiKey, {
    method: "PATCH",
    body: JSON.stringify({ payment_status: "paid" }),
  });
}

export function getCustomers(salonId: string, apiKey: string) {
  return request<Customer[]>(`/api/salons/${salonId}/customers`, apiKey);
}

// ── Broadcasts ────────────────────────────────────────────────────────────────

export function getBroadcasts(salonId: string, apiKey: string) {
  return request<Broadcast[]>(`/api/salons/${salonId}/broadcasts`, apiKey);
}

export function createBroadcast(salonId: string, data: BroadcastCreate, apiKey: string) {
  return request<Broadcast>(`/api/salons/${salonId}/broadcasts`, apiKey, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function sendBroadcast(salonId: string, broadcastId: string, apiKey: string, customerIds?: string[]) {
  const opts: RequestInit = { method: "POST" };
  if (customerIds !== undefined) {
    opts.body = JSON.stringify({ customer_ids: customerIds });
  }
  return request(`/api/salons/${salonId}/broadcasts/${broadcastId}/send`, apiKey, opts);
}

export function updateBroadcast(salonId: string, broadcastId: string, data: { message_text?: string; image_url?: string | null }, apiKey: string) {
  return request<Broadcast>(`/api/salons/${salonId}/broadcasts/${broadcastId}`, apiKey, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function uploadBroadcastImage(salonId: string, file: File, apiKey: string): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/salons/${salonId}/broadcasts/upload-image`, {
    method: "POST",
    headers: { "X-API-Key": apiKey },
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new ApiError(body.detail || "Upload failed", res.status);
  }
  const data = await res.json();
  return data.url as string;
}

// ── Settings ─────────────────────────────────────────────────────────────────

export function getSettings(salonId: string, apiKey: string) {
  return request<SalonSettings>(`/api/salons/${salonId}/settings`, apiKey);
}

export function updateSettings(salonId: string, data: Partial<SalonSettings>, apiKey: string) {
  return request<SalonSettings>(`/api/salons/${salonId}/settings`, apiKey, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function updateSalon(salonId: string, data: { owner_name?: string; salon_name?: string; upi_id?: string }, apiKey: string) {
  return request<Salon>(`/api/salons/${salonId}`, apiKey, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ── Types ─────────────────────────────────────────────────────────────────────

export type Salon = {
  id: string;
  owner_phone: string;
  owner_name: string;
  salon_name: string;
  upi_id?: string;
  plan_type: string;
  api_key?: string;
};

export type Appointment = {
  id: string;
  salon_id: string;
  customer_id: string;
  staff_id: string;
  service_id: string;
  appointment_date: string;
  appointment_time: string;
  status: "confirmed" | "completed" | "cancelled" | "no_show";
  created_at: string;
};

export type Service = {
  id: string;
  service_name: string;
  price: number; // paise
  duration_minutes: number;
  is_active: boolean;
};

export type ServiceCreate = {
  service_name: string;
  price: number; // paise
  duration_minutes: number;
};

export type Staff = {
  id: string;
  staff_name: string;
  phone?: string;
  is_active: boolean;
};

export type StaffCreate = {
  staff_name: string;
  phone?: string;
};

export type Invoice = {
  id: string;
  customer_id: string;
  amount: number; // paise
  description?: string;
  payment_status: "paid" | "unpaid";
  created_at: string;
  paid_at?: string;
  pdf_url?: string;
};

export type InvoiceCreate = {
  customer_id: string;
  amount: number; // paise
  description?: string;
  appointment_id?: string;
  payment_status?: "paid" | "unpaid";
};

export type Customer = {
  id: string;
  phone: string;
  customer_name: string;
  opted_out_broadcasts: boolean;
};

export type Broadcast = {
  id: string;
  message_text: string;
  image_url?: string;
  sent_count: number;
  created_at: string;
};

export type BroadcastCreate = {
  message_text: string;
  image_url?: string;
  headline?: string;
};

export type SalonSettings = {
  opening_time: string;
  closing_time: string;
  days_advance_booking: number;
  min_advance_booking_minutes: number;
  max_concurrent?: number;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

export const paiseToRupees = (paise: number) =>
  `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const rupeesToPaise = (rupees: number) => Math.round(rupees * 100);

export { ApiError };
