"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  getBroadcasts,
  createBroadcast,
  updateBroadcast,
  sendBroadcast,
  uploadBroadcastImage,
  getCustomers,
  type Broadcast,
  type Customer,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Send, Users, ImageIcon, X, Upload, Pencil, Loader2 } from "lucide-react";

// ── Image upload helpers ───────────────────────────────────────────────────────

function ImageDropZone({
  preview,
  onFile,
  onClear,
  dragOver,
  onDragOver,
  onDragLeave,
  onDrop,
  fileRef,
}: {
  preview: string | null;
  onFile: (f: File) => void;
  onClear: () => void;
  dragOver: boolean;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent) => void;
  fileRef: React.RefObject<HTMLInputElement | null>;
}) {
  return (
    <div className="space-y-1.5">
      <Label>Image (optional)</Label>
      {preview ? (
        <div className="relative rounded-lg overflow-hidden border border-zinc-200">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={preview} alt="Preview" className="w-full max-h-48 object-cover" />
          <button
            type="button"
            onClick={onClear}
            className="absolute top-2 right-2 rounded-full bg-black/60 p-1 text-white hover:bg-black/80"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <div
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed py-6 text-sm transition-colors ${
            dragOver
              ? "border-zinc-400 bg-zinc-50"
              : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50"
          }`}
        >
          <Upload className="h-6 w-6 text-zinc-400" />
          <span className="text-zinc-500">
            Drag & drop or <span className="text-zinc-900 font-medium">click to upload</span>
          </span>
          <span className="text-xs text-zinc-400">JPEG, PNG, WebP — max 5 MB</span>
        </div>
      )}
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function BroadcastsPage() {
  const { salon, apiKey } = useAuth();
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([]);
  const [loading, setLoading] = useState(true);
  const [successMsg, setSuccessMsg] = useState("");

  // ── Create dialog ────────────────────────────────────────────────────────────
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ message_text: "" });
  const [createImageFile, setCreateImageFile] = useState<File | null>(null);
  const [createImagePreview, setCreateImagePreview] = useState<string | null>(null);
  const [createDragOver, setCreateDragOver] = useState(false);
  const [createUploading, setCreateUploading] = useState(false);
  const [createSaving, setCreateSaving] = useState(false);
  const [createError, setCreateError] = useState("");
  const createFileRef = useRef<HTMLInputElement>(null);

  // ── Edit dialog ──────────────────────────────────────────────────────────────
  const [editBc, setEditBc] = useState<Broadcast | null>(null);
  const [editMessage, setEditMessage] = useState("");
  const [editExistingUrl, setEditExistingUrl] = useState<string | null>(null);
  const [editImageFile, setEditImageFile] = useState<File | null>(null);
  const [editImagePreview, setEditImagePreview] = useState<string | null>(null);
  const [editDragOver, setEditDragOver] = useState(false);
  const [editUploading, setEditUploading] = useState(false);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");
  const editFileRef = useRef<HTMLInputElement>(null);

  // ── Send dialog ──────────────────────────────────────────────────────────────
  const [sendBc, setSendBc] = useState<Broadcast | null>(null);
  const [sendCustomers, setSendCustomers] = useState<Customer[]>([]);
  const [sendLoading, setSendLoading] = useState(false);
  const [sendError, setSendError] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sending, setSending] = useState(false);

  // ── Load broadcasts ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!salon || !apiKey) return;
    getBroadcasts(salon.id, apiKey)
      .then(setBroadcasts)
      .catch(() => setBroadcasts([]))
      .finally(() => setLoading(false));
  }, [salon, apiKey]);

  // ── Load customers when send dialog opens ────────────────────────────────────
  useEffect(() => {
    if (!sendBc || !salon || !apiKey) return;
    setSendLoading(true);
    setSendError("");
    getCustomers(salon.id, apiKey)
      .then((customers) => {
        setSendCustomers(customers);
        setSelectedIds(new Set(customers.filter((c) => !c.opted_out_broadcasts).map((c) => c.id)));
      })
      .catch(() => setSendError("Failed to load customers."))
      .finally(() => setSendLoading(false));
  }, [sendBc, salon, apiKey]);

  // ── Image helpers ────────────────────────────────────────────────────────────
  const validateFile = (file: File, setError: (e: string) => void): boolean => {
    if (!file.type.startsWith("image/")) { setError("Only image files are allowed."); return false; }
    if (file.size > 5 * 1024 * 1024) { setError("Image must be under 5 MB."); return false; }
    return true;
  };

  // ── Create handlers ──────────────────────────────────────────────────────────
  const handleCreateFile = (file: File) => {
    if (!validateFile(file, setCreateError)) return;
    setCreateError("");
    setCreateImageFile(file);
    setCreateImagePreview(URL.createObjectURL(file));
  };

  const clearCreateImage = () => {
    setCreateImageFile(null);
    if (createImagePreview) URL.revokeObjectURL(createImagePreview);
    setCreateImagePreview(null);
    if (createFileRef.current) createFileRef.current.value = "";
  };

  const resetCreate = () => {
    setCreateForm({ message_text: "" });
    clearCreateImage();
    setCreateError("");
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salon || !apiKey) return;
    setCreateError("");
    setCreateSaving(true);
    let imageUrl: string | undefined;
    if (createImageFile) {
      setCreateUploading(true);
      try {
        imageUrl = await uploadBroadcastImage(salon.id, createImageFile, apiKey);
      } catch (err: unknown) {
        setCreateError(err instanceof Error ? err.message : "Image upload failed.");
        setCreateSaving(false);
        setCreateUploading(false);
        return;
      }
      setCreateUploading(false);
    }
    try {
      const bc = await createBroadcast(salon.id, { message_text: createForm.message_text.trim(), image_url: imageUrl }, apiKey);
      setBroadcasts((prev) => [bc, ...prev]);
      resetCreate();
      setCreateOpen(false);
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Failed to create broadcast.");
    } finally {
      setCreateSaving(false);
    }
  };

  // ── Edit handlers ────────────────────────────────────────────────────────────
  const openEdit = (bc: Broadcast) => {
    setEditBc(bc);
    setEditMessage(bc.message_text);
    setEditExistingUrl(bc.image_url || null);
    setEditImageFile(null);
    setEditImagePreview(bc.image_url || null);
    setEditError("");
  };

  const handleEditFile = (file: File) => {
    if (!validateFile(file, setEditError)) return;
    setEditError("");
    setEditImageFile(file);
    if (editImagePreview && editImagePreview !== editExistingUrl) URL.revokeObjectURL(editImagePreview);
    setEditImagePreview(URL.createObjectURL(file));
  };

  const clearEditImage = () => {
    setEditImageFile(null);
    if (editImagePreview && editImagePreview !== editExistingUrl) URL.revokeObjectURL(editImagePreview);
    setEditImagePreview(null);
    setEditExistingUrl(null);
    if (editFileRef.current) editFileRef.current.value = "";
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salon || !apiKey || !editBc) return;
    setEditError("");
    setEditSaving(true);
    let finalImageUrl: string | null = editExistingUrl;
    if (editImageFile) {
      setEditUploading(true);
      try {
        finalImageUrl = await uploadBroadcastImage(salon.id, editImageFile, apiKey);
      } catch (err: unknown) {
        setEditError(err instanceof Error ? err.message : "Image upload failed.");
        setEditSaving(false);
        setEditUploading(false);
        return;
      }
      setEditUploading(false);
    }
    try {
      const updated = await updateBroadcast(salon.id, editBc.id, {
        message_text: editMessage.trim(),
        image_url: finalImageUrl,
      }, apiKey);
      setBroadcasts((prev) => prev.map((b) => b.id === updated.id ? updated : b));
      setEditBc(null);
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : "Failed to update broadcast.");
    } finally {
      setEditSaving(false);
    }
  };

  // ── Send handlers ────────────────────────────────────────────────────────────
  const eligibleCount = sendCustomers.filter((c) => !c.opted_out_broadcasts).length;
  const allSelected = eligibleCount > 0 && selectedIds.size === eligibleCount;

  const toggleAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(sendCustomers.filter((c) => !c.opted_out_broadcasts).map((c) => c.id)));
    }
  };

  const handleSend = async () => {
    if (!salon || !apiKey || !sendBc) return;
    setSending(true);
    try {
      const result = await sendBroadcast(salon.id, sendBc.id, apiKey, Array.from(selectedIds)) as { recipients: number; message: string };
      setSendBc(null);
      if (result.recipients === 0) {
        setSuccessMsg("No customers to send to yet. Customers are added automatically when they book via WhatsApp.");
      } else {
        setSuccessMsg(`Queued — sending to ${result.recipients} customer${result.recipients === 1 ? "" : "s"}.`);
      }
      setTimeout(() => setSuccessMsg(""), 7000);
    } catch (err: unknown) {
      setSendError(err instanceof Error ? err.message : "Failed to send broadcast.");
    } finally {
      setSending(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Broadcasts</h1>
        <Dialog open={createOpen} onOpenChange={(v) => { setCreateOpen(v); if (!v) resetCreate(); }}>
          <DialogTrigger render={<Button size="sm" />}>
            <Plus className="h-4 w-4 mr-1" />
            New Broadcast
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Create Broadcast</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4 mt-2">
              <ImageDropZone
                preview={createImagePreview}
                onFile={handleCreateFile}
                onClear={clearCreateImage}
                dragOver={createDragOver}
                onDragOver={(e) => { e.preventDefault(); setCreateDragOver(true); }}
                onDragLeave={() => setCreateDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setCreateDragOver(false); const f = e.dataTransfer.files[0]; if (f) handleCreateFile(f); }}
                fileRef={createFileRef}
              />
              <div className="space-y-1.5">
                <Label htmlFor="bc_message">Message</Label>
                <Textarea
                  id="bc_message"
                  placeholder="Hi! We have an exciting offer this weekend…"
                  value={createForm.message_text}
                  onChange={(e) => setCreateForm({ message_text: e.target.value })}
                  rows={4}
                  required
                />
                <p className="text-xs text-zinc-400 text-right">{createForm.message_text.length}/500</p>
              </div>
              {createError && <p className="text-sm text-destructive">{createError}</p>}
              <DialogFooter>
                <Button type="submit" disabled={createSaving}>
                  {createUploading ? "Uploading image…" : createSaving ? "Creating…" : "Create Broadcast"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {successMsg && (
        <div className="rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700 flex items-start gap-2">
          <span className="flex-1">{successMsg}</span>
          <button onClick={() => setSuccessMsg("")} className="text-green-500 hover:text-green-700 shrink-0">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            All Broadcasts
            {!loading && <span className="ml-2 text-zinc-400 font-normal">({broadcasts.length})</span>}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-lg border border-zinc-100 p-4 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                  <div className="flex gap-2 pt-1">
                    <Skeleton className="h-5 w-16" />
                    <Skeleton className="h-5 w-20" />
                  </div>
                </div>
              ))}
            </div>
          ) : broadcasts.length === 0 ? (
            <p className="text-sm text-zinc-400 py-8 text-center">
              No broadcasts yet. Create your first message to customers.
            </p>
          ) : (
            <div className="space-y-3">
              {broadcasts.map((bc) => (
                <div key={bc.id} className="rounded-lg border border-zinc-200 p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm text-zinc-800 leading-relaxed flex-1">{bc.message_text}</p>
                    <div className="flex gap-1.5 shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openEdit(bc)}
                      >
                        <Pencil className="h-3.5 w-3.5 mr-1" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => { setSendBc(bc); setSendError(""); }}
                      >
                        <Send className="h-3.5 w-3.5 mr-1" />
                        Send
                      </Button>
                    </div>
                  </div>
                  {bc.image_url && (
                    <div className="rounded overflow-hidden border border-zinc-100 max-w-[200px]">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={bc.image_url} alt="Broadcast image" className="w-full object-cover max-h-28" />
                    </div>
                  )}
                  <div className="flex items-center gap-3 text-xs text-zinc-400">
                    <span className="flex items-center gap-1">
                      <Users className="h-3 w-3" />
                      {bc.sent_count} sent
                    </span>
                    <span>{new Date(bc.created_at).toLocaleDateString("en-IN")}</span>
                    {bc.image_url && (
                      <Badge variant="outline" className="text-xs gap-1">
                        <ImageIcon className="h-2.5 w-2.5" /> Image
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Edit dialog ──────────────────────────────────────────────────────── */}
      <Dialog open={!!editBc} onOpenChange={(v) => { if (!v) setEditBc(null); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Broadcast</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEdit} className="space-y-4 mt-2">
            <ImageDropZone
              preview={editImagePreview}
              onFile={handleEditFile}
              onClear={clearEditImage}
              dragOver={editDragOver}
              onDragOver={(e) => { e.preventDefault(); setEditDragOver(true); }}
              onDragLeave={() => setEditDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setEditDragOver(false); const f = e.dataTransfer.files[0]; if (f) handleEditFile(f); }}
              fileRef={editFileRef}
            />
            <div className="space-y-1.5">
              <Label htmlFor="edit_bc_message">Message</Label>
              <Textarea
                id="edit_bc_message"
                value={editMessage}
                onChange={(e) => setEditMessage(e.target.value)}
                rows={4}
                required
              />
              <p className="text-xs text-zinc-400 text-right">{editMessage.length}/500</p>
            </div>
            {editError && <p className="text-sm text-destructive">{editError}</p>}
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setEditBc(null)}>Cancel</Button>
              <Button type="submit" disabled={editSaving}>
                {editUploading ? "Uploading…" : editSaving ? "Saving…" : "Save Changes"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── Send dialog ──────────────────────────────────────────────────────── */}
      <Dialog open={!!sendBc} onOpenChange={(v) => { if (!v) { setSendBc(null); setSendCustomers([]); setSelectedIds(new Set()); setSendError(""); } }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Send Broadcast</DialogTitle>
          </DialogHeader>

          {/* Message preview */}
          {sendBc && (
            <div className="rounded-lg bg-zinc-50 border border-zinc-200 px-3 py-2 text-sm text-zinc-600 line-clamp-3">
              {sendBc.message_text}
            </div>
          )}

          <div className="space-y-2">
            <p className="text-sm font-medium text-zinc-700">Recipients</p>

            {sendLoading ? (
              <div className="flex items-center justify-center py-6 gap-2 text-zinc-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">Loading customers…</span>
              </div>
            ) : sendError ? (
              <p className="text-sm text-destructive py-4 text-center">{sendError}</p>
            ) : sendCustomers.length === 0 ? (
              <p className="text-sm text-zinc-400 py-4 text-center">
                No customers yet. They are added automatically when they book via WhatsApp.
              </p>
            ) : (
              <div className="rounded-lg border border-zinc-200 overflow-hidden">
                {/* Select all */}
                <label className="flex items-center gap-3 px-3 py-2.5 bg-zinc-50 border-b border-zinc-200 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-zinc-900 cursor-pointer"
                    checked={allSelected}
                    disabled={eligibleCount === 0}
                    onChange={toggleAll}
                  />
                  <span className="text-sm font-medium text-zinc-700">
                    Select all
                    <span className="ml-1 font-normal text-zinc-400">({eligibleCount} eligible)</span>
                  </span>
                </label>

                {/* Customer list */}
                <div className="max-h-48 overflow-y-auto divide-y divide-zinc-100">
                  {sendCustomers.map((c) => (
                    <label
                      key={c.id}
                      className={`flex items-center gap-3 px-3 py-2.5 select-none ${
                        c.opted_out_broadcasts ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:bg-zinc-50"
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-zinc-900 cursor-pointer"
                        checked={selectedIds.has(c.id)}
                        disabled={c.opted_out_broadcasts}
                        onChange={(e) => {
                          setSelectedIds((prev) => {
                            const next = new Set(prev);
                            if (e.target.checked) next.add(c.id);
                            else next.delete(c.id);
                            return next;
                          });
                        }}
                      />
                      <span className="text-sm text-zinc-800 flex-1">{c.customer_name}</span>
                      <span className="text-xs text-zinc-400">
                        {c.opted_out_broadcasts ? "opted out" : c.phone}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          {sendError && !sendLoading && (
            <p className="text-sm text-destructive">{sendError}</p>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setSendBc(null)} disabled={sending}>
              Cancel
            </Button>
            <Button
              onClick={handleSend}
              disabled={sending || sendLoading || selectedIds.size === 0}
            >
              {sending ? (
                <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />Sending…</>
              ) : (
                <>
                  <Send className="h-3.5 w-3.5 mr-1" />
                  Send to {selectedIds.size} customer{selectedIds.size === 1 ? "" : "s"}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
