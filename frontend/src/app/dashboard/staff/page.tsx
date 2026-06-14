"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getStaff, createStaff, updateStaff, deleteStaff, type Staff } from "@/lib/api";
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

export default function StaffPage() {
  const { salon, apiKey } = useAuth();
  const [staff, setStaff] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ staff_name: "", phone: "" });
  const [createSaving, setCreateSaving] = useState(false);
  const [createError, setCreateError] = useState("");

  // Edit dialog
  const [editMember, setEditMember] = useState<Staff | null>(null);
  const [editForm, setEditForm] = useState({ staff_name: "", phone: "" });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");

  // Delete confirm
  const [deleteTarget, setDeleteTarget] = useState<Staff | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    if (!salon || !apiKey) return;
    getStaff(salon.id, apiKey)
      .then(setStaff)
      .catch(() => setStaff([]))
      .finally(() => setLoading(false));
  }, [salon, apiKey]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salon || !apiKey) return;
    setCreateError("");
    setCreateSaving(true);
    try {
      const member = await createStaff(salon.id, {
        staff_name: createForm.staff_name.trim(),
        phone: createForm.phone.trim() || undefined,
      }, apiKey);
      setStaff((prev) => [...prev, member]);
      setCreateForm({ staff_name: "", phone: "" });
      setCreateOpen(false);
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Failed to add staff.");
    } finally {
      setCreateSaving(false);
    }
  };

  const openEdit = (member: Staff) => {
    setEditMember(member);
    setEditForm({ staff_name: member.staff_name, phone: member.phone || "" });
    setEditError("");
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salon || !apiKey || !editMember) return;
    setEditError("");
    setEditSaving(true);
    try {
      const updated = await updateStaff(salon.id, editMember.id, {
        staff_name: editForm.staff_name.trim(),
        phone: editForm.phone.trim() || undefined,
      }, apiKey);
      setStaff((prev) => prev.map((s) => s.id === updated.id ? updated : s));
      setEditMember(null);
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : "Failed to update staff.");
    } finally {
      setEditSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!salon || !apiKey || !deleteTarget) return;
    setDeleteLoading(true);
    try {
      await deleteStaff(salon.id, deleteTarget.id, apiKey);
      setStaff((prev) => prev.filter((s) => s.id !== deleteTarget.id));
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
        <h1 className="text-2xl font-semibold tracking-tight">Staff</h1>
        <Dialog open={createOpen} onOpenChange={(v) => { setCreateOpen(v); if (!v) { setCreateForm({ staff_name: "", phone: "" }); setCreateError(""); } }}>
          <DialogTrigger render={<Button size="sm" />}>
            <Plus className="h-4 w-4 mr-1" />
            Add Staff
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Staff Member</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4 mt-2">
              <div className="space-y-1.5">
                <Label htmlFor="staff_name">Name</Label>
                <Input
                  id="staff_name"
                  placeholder="e.g. Rahul"
                  value={createForm.staff_name}
                  onChange={(e) => setCreateForm((f) => ({ ...f, staff_name: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="staff_phone">Phone (optional)</Label>
                <Input
                  id="staff_phone"
                  type="tel"
                  placeholder="10-digit number"
                  value={createForm.phone}
                  onChange={(e) => setCreateForm((f) => ({ ...f, phone: e.target.value }))}
                />
              </div>
              {createError && <p className="text-sm text-destructive">{createError}</p>}
              <DialogFooter>
                <Button type="submit" disabled={createSaving}>
                  {createSaving ? "Adding…" : "Add Staff"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            All Staff
            {!loading && <span className="ml-2 text-zinc-400 font-normal">({staff.length})</span>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {[1, 2, 3].map((i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-14" /></TableCell>
                    <TableCell><Skeleton className="h-6 w-12" /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : staff.length === 0 ? (
            <p className="text-sm text-zinc-400 py-8 text-center">No staff yet. Add your first team member.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {staff.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell className="font-medium">{member.staff_name}</TableCell>
                    <TableCell className="text-zinc-500">{member.phone || "—"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={member.is_active ? "bg-green-50 text-green-700 border-green-200" : "bg-zinc-100 text-zinc-500"}>
                        {member.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          className="text-zinc-400 hover:text-zinc-700"
                          onClick={() => openEdit(member)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          className="text-zinc-400 hover:text-destructive"
                          onClick={() => setDeleteTarget(member)}
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
      <Dialog open={!!editMember} onOpenChange={(v) => { if (!v) setEditMember(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Staff Member</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEdit} className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label htmlFor="edit_staff_name">Name</Label>
              <Input
                id="edit_staff_name"
                value={editForm.staff_name}
                onChange={(e) => setEditForm((f) => ({ ...f, staff_name: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit_staff_phone">Phone (optional)</Label>
              <Input
                id="edit_staff_phone"
                type="tel"
                placeholder="10-digit number"
                value={editForm.phone}
                onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
              />
            </div>
            {editError && <p className="text-sm text-destructive">{editError}</p>}
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setEditMember(null)}>Cancel</Button>
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
        title="Remove staff member"
        description={`Remove "${deleteTarget?.staff_name}" from your team? This cannot be undone.`}
        confirmLabel="Remove"
        destructive
        loading={deleteLoading}
        onConfirm={handleDelete}
      />
    </div>
  );
}
