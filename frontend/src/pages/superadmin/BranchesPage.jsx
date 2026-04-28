import { useState, useEffect, useCallback } from "react";
import {
  listBranches,
  createBranch,
  updateBranch,
  deleteBranch,
  listRoomTypes,
  createRoomType,
  updateRoomType,
  deleteRoomType,
  listRooms,
  createRoom,
  updateRoom,
  deleteRoom,
  uploadRoomImages,
  deleteRoomImage,
  MAX_ROOM_IMAGES,
} from "../../services/branchesService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Select from "../../components/Select";
import Modal from "../../components/Modal";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";
import ImageCarousel from "../../components/ImageCarousel";

const ROOM_STATUS_OPTIONS = [
  { value: "available", label: "Available" },
  { value: "booked", label: "Booked" },
  { value: "occupied", label: "Occupied" },
  { value: "cleaning", label: "Cleaning" },
  { value: "ready", label: "Ready" },
];

function BranchesPage() {
  const toast = useToast();
  const [branches, setBranches] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [selectedBranchId, setSelectedBranchId] = useState(null);
  const [typesModalOpen, setTypesModalOpen] = useState(false);
  const [busyId, setBusyId] = useState(null);

  // Generic modal
  const [modalKind, setModalKind] = useState(null); // "branch" | "room-type" | "room"
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [b, rt, r] = await Promise.all([
        listBranches(),
        listRoomTypes(),
        listRooms(),
      ]);
      setBranches(b);
      setRoomTypes(rt);
      setRooms(r);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Resolve human-readable name for a room-type FK id when rendering rows
  // in the rooms table below. (Branch names are rendered directly from the
  // selected branch object so no helper is needed for them.)
  const typeName = (id) => roomTypes.find((t) => t.id === id)?.name || `#${id}`;

  // ---------------------------------------------- Open modals
  const openCreate = (kind) => {
    setModalKind(kind);
    setEditing(null);
    if (kind === "branch") setForm({
      name: "", location: "", is_active: true, image_file: null,
      working_days_per_month: 26, monthly_expense_limit: "0",
    });
    if (kind === "room-type") setForm({ name: "" });
    if (kind === "room") {
      let defaultBranchId = "";
      if (selectedBranchId) defaultBranchId = String(selectedBranchId);
      else if (branches[0]) defaultBranchId = String(branches[0].id);
      setForm({
        branch: defaultBranchId,
        room_type: roomTypes[0] ? String(roomTypes[0].id) : "",
        room_number: "",
        base_price: "",
        is_active: true,
        image_files: [],
      });
    }
  };

  const openEdit = (kind, row) => {
    setModalKind(kind);
    setEditing(row);
    if (kind === "branch") setForm({
      name: row.name,
      location: row.location || "",
      is_active: row.is_active,
      image_file: null,
      existing_image_url: row.image_url || null,
      working_days_per_month: row.working_days_per_month ?? 26,
      monthly_expense_limit: row.monthly_expense_limit ?? "0",
    });
    if (kind === "room-type") setForm({ name: row.name });
    if (kind === "room") setForm({
      branch: String(row.branch),
      room_type: String(row.room_type),
      room_number: row.room_number,
      base_price: row.base_price == null ? "" : String(row.base_price),
      is_active: row.is_active,
      image_files: [],
      existing_images: row.images || [],
    });
  };

  const closeModal = () => { setModalKind(null); setEditing(null); };

  // ---------------------------------------------- Submit
  const submitBranch = async () => {
    const payload = {
      name: form.name.trim(),
      location: form.location.trim(),
      is_active: form.is_active,
      working_days_per_month: Number(form.working_days_per_month) || 26,
      monthly_expense_limit: String(form.monthly_expense_limit ?? "0"),
    };
    if (editing) await updateBranch(editing.id, payload, form.image_file || null);
    else await createBranch(payload, form.image_file || null);
  };

  const submitRoomType = async () => {
    const payload = { name: form.name.trim() };
    if (editing) await updateRoomType(editing.id, payload);
    else await createRoomType(payload);
  };

  const submitRoom = async () => {
    const payload = {
      branch: Number(form.branch),
      room_type: Number(form.room_type),
      room_number: form.room_number.trim(),
      base_price: form.base_price === "" ? "0" : String(form.base_price),
      is_active: form.is_active,
    };
    const saved = editing
      ? await updateRoom(editing.id, payload)
      : await createRoom(payload);
    const roomId = editing ? editing.id : saved?.id;
    const files = form.image_files || [];
    if (roomId && files.length) {
      await uploadRoomImages(roomId, files);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (modalKind === "branch") await submitBranch();
      else if (modalKind === "room-type") await submitRoomType();
      else if (modalKind === "room") await submitRoom();
      toast.success("Saved.");
      closeModal();
      fetchAll();
    } catch (err) {
      const data = err.response?.data;
      const msg = data?.detail
        || (typeof data === "object" ? Object.values(data).flat().join(" ") : null)
        || "Failed to save.";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveExistingImage = async (img) => {
    if (!editing) return;
    try {
      await deleteRoomImage(editing.id, img.id);
      setForm((f) => ({
        ...f,
        existing_images: (f.existing_images || []).filter((i) => i.id !== img.id),
      }));
    } catch {
      toast.error("Failed to remove image.");
    }
  };

  const remove = async (kind, row) => {
    let label;
    if (kind === "branch" || kind === "room-type") label = row.name;
    else label = row.room_number;
    if (!globalThis.confirm(`Delete ${kind} "${label}"?`)) return;
    setBusyId(`${kind}-${row.id}`);
    try {
      if (kind === "branch") await deleteBranch(row.id);
      if (kind === "room-type") await deleteRoomType(row.id);
      if (kind === "room") await deleteRoom(row.id);
      toast.success("Deleted.");
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to delete.");
    } finally {
      setBusyId(null);
    }
  };

  // ---------------------------------------------- Columns
  const submitLabel = editing ? "Save" : "Create";

  const renderModal = () => (
    <Modal
      isOpen={modalKind !== null}
      onClose={closeModal}
      title={editing ? `Edit ${modalKind}` : `New ${modalKind}`}
    >
      <form onSubmit={submit}>
        {modalKind === "branch" && (
          <>
            <Input id="b-name" label="Name" value={form.name || ""} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
            <Input id="b-location" label="Location" value={form.location || ""} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))} />
            <Input id="b-wdays" type="number" min="1" max="31" label="Working days / month"
              value={form.working_days_per_month ?? 26}
              onChange={(e) => setForm((f) => ({ ...f, working_days_per_month: e.target.value }))} />
            <Input id="b-limit" type="number" min="0" step="10000" label="Monthly expense limit (сум)"
              value={form.monthly_expense_limit ?? "0"}
              onChange={(e) => setForm((f) => ({ ...f, monthly_expense_limit: e.target.value }))} />
            <div className="form-group">
              <label className="label" htmlFor="b-image">Branch image</label>
              <input
                id="b-image"
                type="file"
                accept="image/*"
                className="input"
                onChange={(e) => setForm((f) => ({ ...f, image_file: e.target.files?.[0] || null }))}
              />
              {(form.image_file || form.existing_image_url) && (
                <div style={{ marginTop: 8 }}>
                  <img
                    src={form.image_file ? URL.createObjectURL(form.image_file) : form.existing_image_url}
                    alt="Branch preview"
                    style={{ maxHeight: 120, borderRadius: 8, border: "1px solid var(--border)" }}
                  />
                </div>
              )}
            </div>
            <div className="form-group">
              <label className="label" htmlFor="b-active">Status</label>
              <Select
                id="b-active"
                value={String(form.is_active)}
                onChange={(v) => setForm((f) => ({ ...f, is_active: v === "true" }))}
                options={[{ value: "true", label: "Active" }, { value: "false", label: "Inactive" }]}
              />
            </div>
          </>
        )}

        {modalKind === "room-type" && (
          <Input id="t-name" label="Name" value={form.name || ""} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
        )}

        {modalKind === "room" && (
          <>
            <div className="form-group">
              <label className="label" htmlFor="r-branch">Branch</label>
              <Select
                id="r-branch"
                value={form.branch || ""}
                onChange={(v) => setForm((f) => ({ ...f, branch: v }))}
                options={branches.map((b) => ({ value: String(b.id), label: b.name }))}
                placeholder="Select branch"
              />
            </div>
            <div className="form-group">
              <label className="label" htmlFor="r-type">Room type</label>
              <Select
                id="r-type"
                value={form.room_type || ""}
                onChange={(v) => setForm((f) => ({ ...f, room_type: v }))}
                options={roomTypes.map((t) => ({ value: String(t.id), label: t.name }))}
                placeholder="Select type"
              />
            </div>
            <Input id="r-num" label="Room number" value={form.room_number || ""} onChange={(e) => setForm((f) => ({ ...f, room_number: e.target.value }))} required />
            <Input
              id="r-price"
              label="Base price (UZS / night)"
              type="number"
              min="0"
              step="1000"
              value={form.base_price || ""}
              onChange={(e) => setForm((f) => ({ ...f, base_price: e.target.value }))}
              placeholder="e.g. 250000"
            />
            <div className="form-group">
              <label className="label" htmlFor="r-active">Status</label>
              <Select
                id="r-active"
                value={String(form.is_active)}
                onChange={(v) => setForm((f) => ({ ...f, is_active: v === "true" }))}
                options={[{ value: "true", label: "Active" }, { value: "false", label: "Inactive" }]}
              />
            </div>

            {/* Existing photos (edit mode only) */}
            {editing && (form.existing_images?.length > 0) && (
              <div className="form-group">
                <div className="label">Current photos</div>
                <ImageCarousel
                  images={form.existing_images.map((img) => ({ id: img.id, url: img.image_url }))}
                  aspectRatio="16 / 9"
                />
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                  {form.existing_images.map((img, i) => (
                    <button
                      key={img.id}
                      type="button"
                      onClick={() => handleRemoveExistingImage(img)}
                      className="btn btn-ghost btn-sm"
                      style={{ color: "#c12e4d" }}
                    >
                      Г— Remove #{i + 1}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* New uploads — max 3 total */}
            {(() => {
              const existingCount = (form.existing_images || []).length;
              const remaining = Math.max(0, MAX_ROOM_IMAGES - existingCount);
              return (
                <div className="form-group">
                  <label className="label" htmlFor="r-images">
                    Room photos ({existingCount}/{MAX_ROOM_IMAGES} used
                    {remaining > 0 ? ` — add up to ${remaining} more` : " — limit reached"})
                  </label>
                  <input
                    id="r-images"
                    type="file"
                    accept="image/*"
                    multiple
                    disabled={remaining === 0}
                    className="input"
                    onChange={(e) => {
                      const picked = Array.from(e.target.files || []);
                      if (picked.length > remaining) {
                        toast.warning(`Only ${remaining} more image(s) allowed (max ${MAX_ROOM_IMAGES} per room).`);
                      }
                      setForm((f) => ({ ...f, image_files: picked.slice(0, remaining) }));
                    }}
                  />
                  {remaining === 0 && (
                    <small style={{ color: "var(--text-secondary)" }}>
                      Remove an existing photo above to free a slot.
                    </small>
                  )}
                  {(form.image_files || []).length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <ImageCarousel
                        images={form.image_files.map((file, i) => ({
                          id: file.name + file.size + i,
                          url: URL.createObjectURL(file),
                          alt: file.name,
                        }))}
                        aspectRatio="16 / 9"
                      />
                    </div>
                  )}
                </div>
              );
            })()}
          </>
        )}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
          <Button variant="ghost" type="button" onClick={closeModal}>Cancel</Button>
          <Button type="submit" disabled={saving}>{saving ? "Saving…" : submitLabel}</Button>
        </div>
      </form>
    </Modal>
  );

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchAll} />;
  const selectedBranch = selectedBranchId
    ? branches.find((b) => b.id === selectedBranchId)
    : null;
  const branchRooms = selectedBranchId
    ? rooms.filter((r) => r.branch === selectedBranchId)
    : [];

  // ---- Room types management modal -----------------------------------
  const renderTypesModal = () => (
    <Modal
      isOpen={typesModalOpen}
      onClose={() => setTypesModalOpen(false)}
      title="Room types"
    >
      <p className="text-muted" style={{ marginTop: 0, fontSize: 13 }}>
        Reference list used when creating rooms (e.g. Single, Double, Suite).
      </p>
      {roomTypes.length === 0
        ? <div className="empty-state" style={{ padding: 12 }}>No room types yet.</div>
        : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
            {roomTypes.map((t) => (
              <div key={t.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", border: "1px solid var(--border)", borderRadius: 8 }}>
                <span>{t.name}</span>
                <div style={{ display: "flex", gap: 6 }}>
                  <Button size="sm" variant="ghost" onClick={() => { setTypesModalOpen(false); openEdit("room-type", t); }}>Edit</Button>
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={busyId === `room-type-${t.id}`}
                    onClick={() => remove("room-type", t)}
                  >
                    {busyId === `room-type-${t.id}` ? "…" : "Delete"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Button onClick={() => { setTypesModalOpen(false); openCreate("room-type"); }}>+ New room type</Button>
      </div>
    </Modal>
  );

  // ---- Drill-down view: rooms of one branch ---------------------------
  if (selectedBranch) {
    return (
      <div>
        <div className="page-header">
          <div>
            <Button variant="ghost" onClick={() => setSelectedBranchId(null)}>← Back to branches</Button>
            <h1 style={{ margin: "6px 0 0" }}>
              {selectedBranch.name} <span style={{ color: "var(--text-secondary)", fontWeight: 400, fontSize: 16 }}>— Rooms</span>
            </h1>
            <div className="text-muted" style={{ fontSize: 13 }}>
              {selectedBranch.location || "No location set"}
            </div>
          </div>
          <Button onClick={() => openCreate("room")} disabled={!roomTypes.length}>+ New room</Button>
        </div>

        {branchRooms.length === 0 ? (
          <div className="empty-state">
            No rooms in this branch yet.{!roomTypes.length && " Create a room type first."}
          </div>
        ) : (
          <div className="card-grid">
            {branchRooms.map((r) => {
              let slides = [];
              if (r.images && r.images.length > 0) slides = r.images;
              else if (r.primary_image_url) slides = [{ id: "p", url: r.primary_image_url }];
              return (
                <div key={r.id} className="image-card">
                  <div className="image-card__media image-card__media--carousel">
                    <span className="badge badge-info image-card__badge" style={{ textTransform: "capitalize" }}>
                      {r.status}
                    </span>
                    <ImageCarousel
                      images={slides}
                      aspectRatio="16 / 10"
                      showThumbnails={false}
                      emptyLabel="No photos"
                      rounded={false}
                    />
                  </div>
                  <div className="image-card__body">
                    <h3 className="image-card__title">
                      Room {r.room_number}
                      <span className="id-chip id-chip--accent" style={{ marginLeft: 8, verticalAlign: "middle" }} title="Room ID">
                        <span className="id-chip__hash">#</span>
                        <span className="id-chip__num">{r.id}</span>
                      </span>
                    </h3>
                    <div className="image-card__meta">
                      <span>{r.room_type_name || typeName(r.room_type)}</span>
                    </div>
                    <div className="image-card__meta">
                      <strong style={{ color: "var(--text-primary)" }}>
                        {Number(r.base_price || 0).toLocaleString()} UZS / night
                      </strong>
                    </div>
                    <div className="image-card__meta">
                      <span className={`badge badge-sm ${r.is_active ? "badge-success" : "badge-muted"}`}>
                        {r.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                  </div>
                  <div className="image-card__actions">
                    <Button size="sm" variant="ghost" onClick={() => openEdit("room", r)}>Edit</Button>
                    <Button
                      size="sm"
                      variant="danger"
                      disabled={busyId === `room-${r.id}`}
                      onClick={() => remove("room", r)}
                    >
                      {busyId === `room-${r.id}` ? "…" : "Delete"}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {renderModal()}
        {renderTypesModal()}
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1>Branches & Rooms</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <Button variant="ghost" onClick={() => setTypesModalOpen(true)}>
            Manage room types ({roomTypes.length})
          </Button>
          <Button onClick={() => openCreate("branch")}>+ New branch</Button>
        </div>
      </div>

      {(
        branches.length === 0
          ? <div className="empty-state">No branches yet.</div>
          : (
            <div className="card-grid">
              {branches.map((b) => {
                const roomCount = rooms.filter((r) => r.branch === b.id).length;
                return (
                  <div
                    key={b.id}
                    className="image-card image-card--clickable"
                    onClick={() => setSelectedBranchId(b.id)}
                    onKeyDown={(e) => { if (e.key === "Enter") setSelectedBranchId(b.id); }}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="image-card__media">
                      <span className={`badge image-card__badge ${b.is_active ? "badge-success" : "badge-muted"}`}>
                        {b.is_active ? "Active" : "Inactive"}
                      </span>
                      {b.image_url
                        ? <img src={b.image_url} alt={b.name} />
                        : <div className="image-card__media-empty">No image</div>}
                      <span className="image-card__count">{roomCount} room{roomCount === 1 ? "" : "s"}</span>
                    </div>
                    <div className="image-card__body">
                      <h3 className="image-card__title">
                        {b.name}
                        <span className="id-chip id-chip--accent" style={{ marginLeft: 8, verticalAlign: "middle" }} title="Branch ID">
                          <span className="id-chip__hash">#</span>
                          <span className="id-chip__num">{b.id}</span>
                        </span>
                      </h3>
                      <div className="image-card__meta">{b.location || "No location set"}</div>
                    </div>
                    <div className="image-card__actions" onClick={(e) => e.stopPropagation()}>
                      <Button size="sm" variant="ghost" onClick={() => openEdit("branch", b)}>Edit</Button>
                      <Button
                        size="sm"
                        variant="danger"
                        disabled={busyId === `branch-${b.id}`}
                        onClick={() => remove("branch", b)}
                      >
                        {busyId === `branch-${b.id}` ? "…" : "Delete"}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )
      )}

      {renderModal()}
      {renderTypesModal()}
    </div>
  );
}

export default BranchesPage;
