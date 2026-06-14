"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getServices, createService, updateService, deleteService, rupeesToPaise, paiseToRupees, type Service } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Plus, Trash2, Pencil } from "lucide-react";

export default function ServicesPage() {
  const { salon, apiKey } = useAuth();
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ service_name: "", price: "", duration_minutes: "" });
  const [createSaving, setCreateSaving] = useState(false);
  const [createError, setCreateError] = useState("");

  // Edit dialog
  const [editService, setEditService] = useState<Service | null>(null);
  const [editForm, setEditForm] = useState({ service_name: "", price: "", duration_minutes: "" });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");

  // Delete confirm
  const [deleteTarget, setDeleteTarget] = useState<Service | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    if (!salon || !apiKey) return;
    getServices(salon.id, apiKey)
      .then(setServices)
      .catch(() => setServices([]))
      .finally(() => setLoading(false));
  }, [salon, apiKey]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salon || !apiKey) return;
    setCreateError("");
    setCreateSaving(true);
    try {
      const svc = await createService(salon.id, {
        service_name: createForm.service_name.trim(),
        price: rupeesToPaise(parseFloat(createForm.price)),
        duration_minutes: parseInt(createForm.duration_minutes),
      }, apiKey);
      setServices((prev) => [...prev, svc]);
      setCreateForm({ service_name: "", price: "", duration_minutes: "" });
      setCreateOpen(false);
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Failed to create service.");
    } finally {
      setCreateSaving(false);
    }
  };

  const openEdit = (svc: Service) => {
    setEditService(svc);
    setEditForm({
      service_name: svc.service_name,
      price: (svc.price / 100).toString(),
      duration_minutes: svc.duration_minutes.toString(),
    });
    setEditError("");
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salon || !apiKey || !editService) return;
    setEditError("");
    setEditSaving(true);
    try {
      const updated = await updateService(salon.id, editService.id, {
        service_name: editForm.service_name.trim(),
        price: rupeesToPaise(parseFloat(editForm.price)),
        duration_minutes: parseInt(editForm.duration_minutes),
      }, apiKey);
      setServices((prev) => prev.map((s) => s.id === updated.id ? updated : s));
      setEditService(null);
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : "Failed to update service.");
    } finally {
      setEditSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!salon || !apiKey || !deleteTarget) return;
    setDeleteLoading(true);
    try {
      await deleteService(salon.id, deleteTarget.id, apiKey);
      setServices((prev) => prev.filter((s) => s.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch {
      setDeleteTarget(null);
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Services</h1>
        <Dialog open={createOpen} onOpenChange={(v) => { setCreateOpen(v); if (!v) { setCreateForm({ service_name: "", price: "", duration_minutes: "" }); setCreateError(""); } }}>
          <DialogTrigger render={<Button size="sm" />}>
            <Plus className="h-4 w-4 mr-1" />
            Add Service
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Service</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4 mt-2">
              <div className="space-y-1.5">
                <Label htmlFor="svc_name">Service Name</Label>
                <Input
                  id="svc_name"
                  placeholder="e.g. Haircut"
                  value={createForm.service_name}
                  onChange={(e) => setCreateForm((f) => ({ ...f, service_name: e.target.value }))}
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="svc_price">Price (₹)</Label>
                  <Input
                    id="svc_price"
                    type="number"
                    min="1"
                    step="0.01"
                    placeholder="500"
                    value={createForm.price}
                    onChange={(e) => setCreateForm((f) => ({ ...f, price: e.target.value }))}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="svc_dur">Duration (min)</Label>
                  <Input
                    id="svc_dur"
                    type="number"
                    min="5"
                    placeholder="30"
                    value={createForm.duration_minutes}
                    onChange={(e) => setCreateForm((f) => ({ ...f, duration_minutes: e.target.value }))}
                    required
                  />
                </div>
              </div>
              {createError && <p className="text-sm text-destructive">{createError}</p>}
              <DialogFooter>
                <Button type="submit" disabled={createSaving}>
                  {createSaving ? "Saving…" : "Add Service"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            All Services
            {!loading && <span className="ml-2 text-zinc-400 font-normal">({services.length})</span>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {[1, 2, 3, 4].map((i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-14" /></TableCell>
                    <TableCell><Skeleton className="h-6 w-12" /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : services.length === 0 ? (
            <p className="text-sm text-zinc-400 py-8 text-center">No services yet. Add your first service.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {services.map((svc) => (
                  <TableRow key={svc.id}>
                    <TableCell className="font-medium">{svc.service_name}</TableCell>
                    <TableCell>{paiseToRupees(svc.price)}</TableCell>
                    <TableCell>{svc.duration_minutes} min</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={svc.is_active ? "bg-green-50 text-green-700 border-green-200" : "bg-zinc-100 text-zinc-500"}>
                        {svc.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          className="text-zinc-400 hover:text-zinc-700"
                          onClick={() => openEdit(svc)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          className="text-zinc-400 hover:text-destructive"
                          onClick={() => setDeleteTarget(svc)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Edit dialog */}
      <Dialog open={!!editService} onOpenChange={(v) => { if (!v) setEditService(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Service</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEdit} className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label htmlFor="edit_svc_name">Service Name</Label>
              <Input
                id="edit_svc_name"
                value={editForm.service_name}
                onChange={(e) => setEditForm((f) => ({ ...f, service_name: e.target.value }))}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit_svc_price">Price (₹)</Label>
                <Input
                  id="edit_svc_price"
                  type="number"
                  min="1"
                  step="0.01"
                  value={editForm.price}
                  onChange={(e) => setEditForm((f) => ({ ...f, price: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_svc_dur">Duration (min)</Label>
                <Input
                  id="edit_svc_dur"
                  type="number"
                  min="5"
                  value={editForm.duration_minutes}
                  onChange={(e) => setEditForm((f) => ({ ...f, duration_minutes: e.target.value }))}
                  required
                />
              </div>
            </div>
            {editError && <p className="text-sm text-destructive">{editError}</p>}
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setEditService(null)}>Cancel</Button>
              <Button type="submit" disabled={editSaving}>
                {editSaving ? "Saving…" : "Save Changes"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(v) => { if (!v) setDeleteTarget(null); }}
        title="Delete service"
        description={`Delete "${deleteTarget?.service_name}"? This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        loading={deleteLoading}
        onConfirm={handleDelete}
      />
    </div>
  );
}
