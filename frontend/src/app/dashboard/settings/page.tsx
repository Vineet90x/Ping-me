"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getSettings, updateSettings, updateSalon, type SalonSettings } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle } from "lucide-react";

export default function SettingsPage() {
  const { salon, apiKey } = useAuth();
  const [settings, setSettings] = useState<SalonSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savingSalon, setSavingSalon] = useState(false);
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [salonSaved, setSalonSaved] = useState(false);
  const [error, setError] = useState("");

  const [salonForm, setSalonForm] = useState({
    salon_name: "",
    owner_name: "",
    upi_id: "",
  });

  const [hoursForm, setHoursForm] = useState({
    opening_time: "09:00",
    closing_time: "20:00",
    days_advance_booking: "7",
    min_advance_booking_minutes: "60",
    max_concurrent: "",
  });

  useEffect(() => {
    if (!salon || !apiKey) return;
    setSalonForm({
      salon_name: salon.salon_name,
      owner_name: salon.owner_name,
      upi_id: salon.upi_id || "",
    });
    getSettings(salon.id, apiKey)
      .then((s) => {
        setSettings(s);
        setHoursForm({
          opening_time: s.opening_time || "09:00",
          closing_time: s.closing_time || "20:00",
          days_advance_booking: String(s.days_advance_booking ?? 7),
          min_advance_booking_minutes: String(s.min_advance_booking_minutes ?? 60),
          max_concurrent: String(s.max_concurrent ?? ""),
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [salon, apiKey]);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salon || !apiKey) return;
    setError("");
    setSavingSettings(true);
    try {
      const data: Partial<SalonSettings> = {
        opening_time: hoursForm.opening_time,
        closing_time: hoursForm.closing_time,
        days_advance_booking: parseInt(hoursForm.days_advance_booking),
        min_advance_booking_minutes: parseInt(hoursForm.min_advance_booking_minutes),
      };
      if (hoursForm.max_concurrent) {
        data.max_concurrent = parseInt(hoursForm.max_concurrent);
      }
      const updated = await updateSettings(salon.id, data, apiKey);
      setSettings(updated);
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 2500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save settings.");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleSaveSalon = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salon || !apiKey) return;
    setError("");
    setSavingSalon(true);
    try {
      await updateSalon(salon.id, {
        salon_name: salonForm.salon_name.trim(),
        owner_name: salonForm.owner_name.trim(),
        upi_id: salonForm.upi_id.trim() || undefined,
      }, apiKey);
      setSalonSaved(true);
      setTimeout(() => setSalonSaved(false), 2500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update salon info.");
    } finally {
      setSavingSalon(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-xl font-semibold">Settings</h1>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Salon info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Salon Information</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSaveSalon} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="salon_name">Salon Name</Label>
                <Input
                  id="salon_name"
                  value={salonForm.salon_name}
                  onChange={(e) => setSalonForm((f) => ({ ...f, salon_name: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="owner_name">Owner Name</Label>
                <Input
                  id="owner_name"
                  value={salonForm.owner_name}
                  onChange={(e) => setSalonForm((f) => ({ ...f, owner_name: e.target.value }))}
                  required
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="upi_id">UPI ID (for invoices)</Label>
              <Input
                id="upi_id"
                placeholder="yourname@upi"
                value={salonForm.upi_id}
                onChange={(e) => setSalonForm((f) => ({ ...f, upi_id: e.target.value }))}
              />
            </div>
            <div className="flex items-center gap-3">
              <Button type="submit" size="sm" disabled={savingSalon}>
                {savingSalon ? "Saving…" : "Save"}
              </Button>
              {salonSaved && (
                <span className="flex items-center gap-1 text-sm text-green-700">
                  <CheckCircle className="h-4 w-4" /> Saved
                </span>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Business hours */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Business Hours & Booking</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-zinc-400">Loading…</p>
          ) : (
            <form onSubmit={handleSaveSettings} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="open_time">Opening Time</Label>
                  <Input
                    id="open_time"
                    type="time"
                    value={hoursForm.opening_time}
                    onChange={(e) => setHoursForm((f) => ({ ...f, opening_time: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="close_time">Closing Time</Label>
                  <Input
                    id="close_time"
                    type="time"
                    value={hoursForm.closing_time}
                    onChange={(e) => setHoursForm((f) => ({ ...f, closing_time: e.target.value }))}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="days_advance">Days Advance Booking</Label>
                  <Input
                    id="days_advance"
                    type="number"
                    min="1"
                    max="60"
                    value={hoursForm.days_advance_booking}
                    onChange={(e) => setHoursForm((f) => ({ ...f, days_advance_booking: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="min_advance">Min Advance (minutes)</Label>
                  <Input
                    id="min_advance"
                    type="number"
                    min="0"
                    value={hoursForm.min_advance_booking_minutes}
                    onChange={(e) => setHoursForm((f) => ({ ...f, min_advance_booking_minutes: e.target.value }))}
                  />
                </div>
              </div>
              <div className="space-y-1.5 max-w-[200px]">
                <Label htmlFor="max_concurrent">Max Concurrent (optional)</Label>
                <Input
                  id="max_concurrent"
                  type="number"
                  min="1"
                  placeholder="Unlimited"
                  value={hoursForm.max_concurrent}
                  onChange={(e) => setHoursForm((f) => ({ ...f, max_concurrent: e.target.value }))}
                />
              </div>
              <div className="flex items-center gap-3">
                <Button type="submit" size="sm" disabled={savingSettings}>
                  {savingSettings ? "Saving…" : "Save"}
                </Button>
                {settingsSaved && (
                  <span className="flex items-center gap-1 text-sm text-green-700">
                    <CheckCircle className="h-4 w-4" /> Saved
                  </span>
                )}
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      {/* API Key */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">API Key</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-zinc-500 mb-3">Your API key is used to authenticate the dashboard and WhatsApp bot.</p>
          <div className="flex items-center gap-2">
            <Input
              readOnly
              value={apiKey || ""}
              type="password"
              className="font-mono text-xs"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                navigator.clipboard.writeText(apiKey || "");
                alert("Copied to clipboard!");
              }}
            >
              Copy
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
