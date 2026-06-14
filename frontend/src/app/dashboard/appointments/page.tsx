"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getAppointments, updateAppointment, type Appointment } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CheckCircle, XCircle, AlertCircle, RefreshCw } from "lucide-react";

const STATUS_OPTIONS: Appointment["status"][] = ["confirmed", "completed", "cancelled", "no_show"];

function statusBadge(status: Appointment["status"]) {
  const map = {
    confirmed: "bg-blue-50 text-blue-700 border-blue-200",
    completed: "bg-green-50 text-green-700 border-green-200",
    cancelled: "bg-red-50 text-red-700 border-red-200",
    no_show: "bg-zinc-100 text-zinc-600 border-zinc-200",
  };
  const labels = {
    confirmed: "Confirmed",
    completed: "Completed",
    cancelled: "Cancelled",
    no_show: "No Show",
  };
  return (
    <Badge variant="outline" className={map[status]}>
      {labels[status]}
    </Badge>
  );
}

export default function AppointmentsPage() {
  const { salon, apiKey } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterDate, setFilterDate] = useState(new Date().toISOString().split("T")[0]);
  const [filterStatus, setFilterStatus] = useState("");
  const [updating, setUpdating] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState("");
  const [updateError, setUpdateError] = useState("");

  const fetchAppointments = async () => {
    if (!salon || !apiKey) return;
    setLoading(true);
    setFetchError("");
    const params: Record<string, string> = {};
    if (filterDate) params.date = filterDate;
    if (filterStatus) params.status = filterStatus;
    try {
      const data = await getAppointments(salon.id, apiKey, params);
      setAppointments(data);
    } catch {
      setFetchError("Failed to load appointments.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [salon, apiKey, filterDate, filterStatus]);

  const handleStatusChange = async (apptId: string, newStatus: Appointment["status"]) => {
    if (!salon || !apiKey) return;
    setUpdating(apptId);
    setUpdateError("");
    try {
      await updateAppointment(salon.id, apptId, { status: newStatus }, apiKey);
      setAppointments((prev) =>
        prev.map((a) => (a.id === apptId ? { ...a, status: newStatus } : a))
      );
    } catch {
      setUpdateError("Failed to update status. Please try again.");
    } finally {
      setUpdating(null);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Appointments</h1>
        <Button variant="outline" size="sm" onClick={fetchAppointments} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <Input
          type="date"
          value={filterDate}
          onChange={(e) => setFilterDate(e.target.value)}
          className="w-40 text-sm"
        />
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="h-9 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus:border-ring focus:ring-3 focus:ring-ring/50"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1).replace("_", " ")}</option>
          ))}
        </select>
      </div>

      {fetchError && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">
          {fetchError}
        </div>
      )}
      {updateError && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">
          {updateError}
        </div>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            {filterDate ? `Appointments for ${filterDate}` : "All Appointments"}
            {!loading && <span className="ml-2 text-zinc-400 font-normal">({appointments.length})</span>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {[1, 2, 3, 4, 5].map((i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-6 w-24" /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : appointments.length === 0 ? (
            <p className="text-sm text-zinc-400 py-8 text-center">No appointments found.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {appointments
                  .sort((a, b) => {
                    const dateCompare = a.appointment_date.localeCompare(b.appointment_date);
                    if (dateCompare !== 0) return dateCompare;
                    return a.appointment_time.localeCompare(b.appointment_time);
                  })
                  .map((appt) => (
                    <TableRow key={appt.id}>
                      <TableCell className="font-semibold">{appt.appointment_time.slice(0, 5)}</TableCell>
                      <TableCell className="text-zinc-500">{appt.appointment_date}</TableCell>
                      <TableCell>{statusBadge(appt.status)}</TableCell>
                      <TableCell className="text-zinc-400 text-xs font-mono">{appt.id.slice(0, 8)}…</TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          {appt.status === "confirmed" && (
                            <>
                              <Button
                                size="xs"
                                variant="outline"
                                disabled={updating === appt.id}
                                onClick={() => handleStatusChange(appt.id, "completed")}
                              >
                                <CheckCircle className="h-3 w-3 mr-1" />
                                Complete
                              </Button>
                              <Button
                                size="xs"
                                variant="outline"
                                disabled={updating === appt.id}
                                onClick={() => handleStatusChange(appt.id, "no_show")}
                              >
                                <AlertCircle className="h-3 w-3 mr-1" />
                                No Show
                              </Button>
                              <Button
                                size="xs"
                                variant="destructive"
                                disabled={updating === appt.id}
                                onClick={() => handleStatusChange(appt.id, "cancelled")}
                              >
                                <XCircle className="h-3 w-3 mr-1" />
                                Cancel
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
