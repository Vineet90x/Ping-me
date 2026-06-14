"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getAppointments, type Appointment } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CalendarDays, CheckCircle, Clock, XCircle } from "lucide-react";

function statusBadge(status: Appointment["status"]) {
  const map = {
    confirmed: { label: "Confirmed", className: "bg-blue-50 text-blue-700 border-blue-200" },
    completed: { label: "Completed", className: "bg-green-50 text-green-700 border-green-200" },
    cancelled: { label: "Cancelled", className: "bg-red-50 text-red-700 border-red-200" },
    no_show: { label: "No Show", className: "bg-zinc-100 text-zinc-600 border-zinc-200" },
  };
  const v = map[status] ?? map.confirmed;
  return <Badge variant="outline" className={v.className}>{v.label}</Badge>;
}

export default function OverviewPage() {
  const { salon, apiKey } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  const today = new Date().toISOString().split("T")[0];

  useEffect(() => {
    if (!salon || !apiKey) return;
    getAppointments(salon.id, apiKey, { date: today })
      .then(setAppointments)
      .catch(() => setAppointments([]))
      .finally(() => setLoading(false));
  }, [salon, apiKey, today]);

  const confirmed = appointments.filter((a) => a.status === "confirmed").length;
  const completed = appointments.filter((a) => a.status === "completed").length;
  const cancelled = appointments.filter((a) => a.status === "cancelled").length;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-sm text-zinc-500 mt-1">
          {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Today's Total", icon: CalendarDays, iconClass: "text-zinc-400", valueClass: "", value: appointments.length },
          { label: "Confirmed", icon: Clock, iconClass: "text-blue-400", valueClass: "text-blue-700", value: confirmed },
          { label: "Completed", icon: CheckCircle, iconClass: "text-green-400", valueClass: "text-green-700", value: completed },
          { label: "Cancelled", icon: XCircle, iconClass: "text-red-400", valueClass: "text-red-700", value: cancelled },
        ].map(({ label, icon: Icon, iconClass, valueClass, value }) => (
          <Card key={label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-zinc-500">{label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <Icon className={`h-4 w-4 ${iconClass}`} />
                {loading ? (
                  <Skeleton className="h-8 w-10" />
                ) : (
                  <span className={`text-2xl font-bold ${valueClass}`}>{value}</span>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Today's appointments */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Today&apos;s Appointments</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3 py-1">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center justify-between py-2">
                  <div className="space-y-1">
                    <Skeleton className="h-4 w-12" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                  <Skeleton className="h-5 w-20" />
                </div>
              ))}
            </div>
          ) : appointments.length === 0 ? (
            <p className="text-sm text-zinc-400 py-4 text-center">No appointments today.</p>
          ) : (
            <div className="divide-y divide-zinc-100">
              {appointments
                .sort((a, b) => a.appointment_time.localeCompare(b.appointment_time))
                .map((appt) => (
                  <div key={appt.id} className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-semibold">{appt.appointment_time.slice(0, 5)}</p>
                      <p className="text-xs text-zinc-400">{appt.id.slice(0, 8)}…</p>
                    </div>
                    {statusBadge(appt.status)}
                  </div>
                ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Salon info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Your Salon</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 text-sm">
          {[
            { label: "Salon Name", value: salon?.salon_name },
            { label: "Owner", value: salon?.owner_name },
            { label: "Phone", value: salon?.owner_phone },
            { label: "Plan", value: salon?.plan_type },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-xs text-zinc-400 font-medium uppercase tracking-wide">{label}</p>
              <p className="font-semibold mt-0.5 capitalize">{value}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
