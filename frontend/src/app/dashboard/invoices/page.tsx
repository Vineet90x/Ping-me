"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  getInvoices,
  createInvoice,
  markInvoicePaid,
  getCustomers,
  rupeesToPaise,
  paiseToRupees,
  type Invoice,
  type Customer,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, CheckCircle } from "lucide-react";

export default function InvoicesPage() {
  const { salon, apiKey } = useAuth();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [marking, setMarking] = useState<string | null>(null);
  const [form, setForm] = useState({ customer_id: "", amount: "", description: "" });
  const [error, setError] = useState("");
  const [markError, setMarkError] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  useEffect(() => {
    if (!salon || !apiKey) return;
    const params: Record<string, string> = {};
    if (filterStatus) params.payment_status = filterStatus;
    Promise.all([
      getInvoices(salon.id, apiKey, params),
      getCustomers(salon.id, apiKey),
    ])
      .then(([inv, cust]) => {
        setInvoices(inv);
        setCustomers(cust);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [salon, apiKey, filterStatus]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salon || !apiKey) return;
    setError("");
    setSaving(true);
    try {
      const inv = await createInvoice(salon.id, {
        customer_id: form.customer_id,
        amount: rupeesToPaise(parseFloat(form.amount)),
        description: form.description.trim() || undefined,
      }, apiKey);
      setInvoices((prev) => [inv, ...prev]);
      setForm({ customer_id: "", amount: "", description: "" });
      setOpen(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create invoice.");
    } finally {
      setSaving(false);
    }
  };

  const handleMarkPaid = async (id: string) => {
    if (!salon || !apiKey) return;
    setMarking(id);
    setMarkError("");
    try {
      await markInvoicePaid(salon.id, id, apiKey);
      setInvoices((prev) =>
        prev.map((inv) => (inv.id === id ? { ...inv, payment_status: "paid" } : inv))
      );
    } catch {
      setMarkError("Failed to mark invoice as paid. Please try again.");
    } finally {
      setMarking(null);
    }
  };

  const customerName = (id: string) =>
    customers.find((c) => c.id === id)?.customer_name || id.slice(0, 8) + "…";

  const totalRevenue = invoices
    .filter((i) => i.payment_status === "paid")
    .reduce((sum, i) => sum + i.amount, 0);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Invoices</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Revenue collected: <span className="font-semibold text-green-700">{paiseToRupees(totalRevenue)}</span>
          </p>
        </div>
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setForm({ customer_id: "", amount: "", description: "" }); setError(""); } }}>
          <DialogTrigger render={<Button size="sm" />}>
            <Plus className="h-4 w-4 mr-1" />
            New Invoice
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Invoice</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4 mt-2">
              <div className="space-y-1.5">
                <Label htmlFor="inv_customer">Customer</Label>
                <select
                  id="inv_customer"
                  value={form.customer_id}
                  onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))}
                  required
                  className="w-full h-9 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus:border-ring"
                >
                  <option value="">Select customer…</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>{c.customer_name} ({c.phone})</option>
                  ))}
                </select>
                {customers.length === 0 && (
                  <p className="text-xs text-zinc-400">Customers appear after they book via WhatsApp.</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="inv_amount">Amount (₹)</Label>
                <Input
                  id="inv_amount"
                  type="number"
                  min="1"
                  step="0.01"
                  placeholder="500"
                  value={form.amount}
                  onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="inv_desc">Description (optional)</Label>
                <Textarea
                  id="inv_desc"
                  placeholder="Haircut + colour treatment"
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  rows={2}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <DialogFooter>
                <Button type="submit" disabled={saving}>
                  {saving ? "Creating…" : "Create Invoice"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filter */}
      <select
        value={filterStatus}
        onChange={(e) => setFilterStatus(e.target.value)}
        className="h-9 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none"
      >
        <option value="">All invoices</option>
        <option value="paid">Paid</option>
        <option value="unpaid">Unpaid</option>
      </select>

      {markError && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">
          {markError}
        </div>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            Invoices
            {!loading && <span className="ml-2 text-zinc-400 font-normal">({invoices.length})</span>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {[1, 2, 3, 4, 5].map((i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-14" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : invoices.length === 0 ? (
            <p className="text-sm text-zinc-400 py-8 text-center">No invoices yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((inv) => (
                  <TableRow key={inv.id}>
                    <TableCell className="font-medium">{customerName(inv.customer_id)}</TableCell>
                    <TableCell className="font-medium">{paiseToRupees(inv.amount)}</TableCell>
                    <TableCell className="text-zinc-500 max-w-[200px] truncate">{inv.description || "—"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={inv.payment_status === "paid" ? "bg-green-50 text-green-700 border-green-200" : "bg-yellow-50 text-yellow-700 border-yellow-200"}>
                        {inv.payment_status === "paid" ? "Paid" : "Unpaid"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-zinc-500 text-xs">
                      {new Date(inv.created_at).toLocaleDateString("en-IN")}
                    </TableCell>
                    <TableCell>
                      {inv.payment_status === "unpaid" && (
                        <Button
                          size="xs"
                          variant="outline"
                          disabled={marking === inv.id}
                          onClick={() => handleMarkPaid(inv.id)}
                        >
                          <CheckCircle className="h-3 w-3 mr-1" />
                          {marking === inv.id ? "…" : "Mark Paid"}
                        </Button>
                      )}
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
