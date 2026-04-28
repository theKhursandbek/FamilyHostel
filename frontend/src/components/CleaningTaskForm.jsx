import { useEffect, useMemo, useState } from "react";
import PropTypes from "prop-types";
import Modal from "./Modal";
import Button from "./Button";
import Loader from "./Loader";
import Select from "./Select";
import { listRooms } from "../services/branchesService";
import { listStaffForAssignment } from "../services/cleaningService";
import { useToast } from "../context/ToastContext";

const PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
];

/**
 * Create / Edit form for a CleaningTask.
 *
 * Modes:
 *  - mode="create": room + priority + optional staff. Submit -> onSubmit(payload).
 *  - mode="edit":   priority + assignee only (room is locked).
 *
 * Staff assignment is OPTIONAL on create. If left empty, the task starts
 * as "pending" and any staff member can pick it up themselves.
 */
function CleaningTaskForm({ isOpen, onClose, mode, task, branchId, onSubmit, submitting }) {
  const toast = useToast();
  const isEdit = mode === "edit";

  const [rooms, setRooms] = useState([]);
  const [staff, setStaff] = useState([]);
  const [loadingRefs, setLoadingRefs] = useState(true);

  const [roomId, setRoomId] = useState("");
  const [priority, setPriority] = useState("normal");
  const [assignedTo, setAssignedTo] = useState("");

  // Load rooms + only-free staff when modal opens.
  // The backend (?free_for_cleaning=true) excludes staff already on a
  // non-completed cleaning task — same pattern as ?has_active_cleaning=false
  // hides occupied rooms.
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setLoadingRefs(true);
    const roomParams = { has_active_cleaning: false };
    if (!isEdit && branchId) roomParams.branch = branchId;
    Promise.all([
      isEdit ? Promise.resolve([]) : listRooms(roomParams),
      listStaffForAssignment({ freeForCleaning: true }),
    ])
      .then(([roomsData, freeStaff]) => {
        if (cancelled) return;
        setRooms(roomsData ?? []);
        const list = freeStaff ?? [];
        // In edit mode, the currently-assigned staff is "busy" on THIS task,
        // so the backend excludes them. Re-add them so they stay selectable.
        if (isEdit && task?.assigned_to) {
          const currentId = Number(task.assigned_to);
          const alreadyIn = list.some(
            (s) => Number(s.staff_profile_id) === currentId,
          );
          if (!alreadyIn) {
            list.unshift({
              staff_profile_id: currentId,
              full_name: task.assigned_to_name || "Current assignee",
              branch_id: null,
              branch_name: task.branch_name || null,
            });
          }
        }
        setStaff(list);
      })
      .catch(() => {
        if (!cancelled) toast.error("Failed to load form options");
      })
      .finally(() => {
        if (!cancelled) setLoadingRefs(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, isEdit, branchId, task, toast]);

  // Seed values from task in edit mode (or reset on open)
  useEffect(() => {
    if (!isOpen) return;
    if (isEdit && task) {
      setRoomId(String(task.room ?? ""));
      setPriority(task.priority || "normal");
      setAssignedTo(task.assigned_to ? String(task.assigned_to) : "");
    } else {
      setRoomId("");
      setPriority("normal");
      setAssignedTo("");
    }
  }, [isOpen, isEdit, task]);

  // For create: derive selected room → branch (required by backend)
  const selectedRoom = useMemo(
    () => rooms.find((r) => String(r.id) === String(roomId)) || null,
    [rooms, roomId],
  );

  // Filter the (already-free) staff list by the selected room's branch
  // for nicer UX. Backend has already excluded anyone busy on another task.
  const staffForBranch = useMemo(() => {
    if (!selectedRoom?.branch) return staff;
    return staff.filter(
      (s) => !s.branch_id || String(s.branch_id) === String(selectedRoom.branch),
    );
  }, [staff, selectedRoom]);

  const handleSubmit = (e) => {
    e.preventDefault();

    if (isEdit) {
      const payload = {
        priority,
        assigned_to: assignedTo ? Number(assignedTo) : null,
      };
      onSubmit(payload);
      return;
    }

    if (!roomId) {
      toast.warning("Please select a room");
      return;
    }
    if (!selectedRoom) {
      toast.warning("Selected room not found");
      return;
    }

    const payload = {
      room: Number(roomId),
      branch: Number(selectedRoom.branch),
      priority,
    };
    if (assignedTo) {
      payload.assigned_to = Number(assignedTo);
    }
    onSubmit(payload);
  };

  let submitLabel;
  if (submitting) {
    submitLabel = "Saving…";
  } else if (isEdit) {
    submitLabel = "Save Changes";
  } else {
    submitLabel = "Create Task";
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? `Edit Cleaning Task #${task?.id ?? ""}` : "New Cleaning Task"}
    >
      {loadingRefs ? (
        <div style={{ padding: 24 }}><Loader /></div>
      ) : (
        <form onSubmit={handleSubmit} className="cl-form">
          <p className="cl-form__lede">
            {isEdit
              ? "Adjust priority or reassign this housekeeping task."
              : "Compose a new housekeeping task. Leave the assignee empty to let any staff member claim it."}
          </p>

          {/* Room */}
          {isEdit ? (
            <div className="cl-form__row">
              <span className="cl-form__lbl">Room</span>
              <div className="cl-form__readonly">
                <span className="cl-form__crest" aria-hidden>{task?.room_number ?? "·"}</span>
                <span className="cl-form__readonly-text">
                  {task?.branch_name || "Housekeeping"}
                </span>
              </div>
            </div>
          ) : (
            <div className="cl-form__row">
              <label htmlFor="cl-room" className="cl-form__lbl">Room <span className="cl-form__req">*</span></label>
              <Select
                id="cl-room"
                value={roomId}
                onChange={(v) => setRoomId(v)}
                placeholder="— Select a room —"
                options={rooms.map((r) => {
                  const branchPart = r.branch_name ? ` · ${r.branch_name}` : "";
                  const statusPart = r.status ? ` (${r.status})` : "";
                  return {
                    value: r.id,
                    label: `Room ${r.room_number}${branchPart}${statusPart}`,
                  };
                })}
              />
            </div>
          )}

          {/* Priority */}
          <div className="cl-form__row">
            <label htmlFor="cl-priority" className="cl-form__lbl">
              Priority <span className="cl-form__req">*</span>
            </label>
            <div className="cl-form__seg" role="radiogroup" aria-label="Priority">
              {PRIORITY_OPTIONS.map((p) => (
                <button
                  type="button"
                  key={p.value}
                  role="radio"
                  aria-checked={priority === p.value}
                  className={`cl-form__seg-btn cl-form__seg-btn--${p.value}${priority === p.value ? " is-on" : ""}`}
                  onClick={() => setPriority(p.value)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Assignee (optional) */}
          <div className="cl-form__row">
            <label htmlFor="cl-staff" className="cl-form__lbl">
              Assign Staff <span className="cl-form__opt">— optional</span>
            </label>
            <Select
              id="cl-staff"
              value={assignedTo}
              onChange={(v) => setAssignedTo(v)}
              placeholder={
                staffForBranch.length === 0
                  ? "— No free staff available —"
                  : "— Leave open for self-pickup —"
              }
              options={staffForBranch.map((s) => {
                const branchPart = s.branch_name ? ` · ${s.branch_name}` : "";
                return {
                  value: s.staff_profile_id,
                  label: `${s.full_name}${branchPart}`,
                };
              })}
            />
            <p className="cl-form__hint">
              {isEdit
                ? "Change or clear the assignee. Staff already on another active task are hidden."
                : "If left empty, any free staff member can pick this task up themselves. Busy staff are hidden."}
            </p>
          </div>

          <hr className="cl-form__rule" />

          <div className="cl-form__actions">
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitLabel}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

CleaningTaskForm.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  mode: PropTypes.oneOf(["create", "edit"]).isRequired,
  branchId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  task: PropTypes.shape({
    id: PropTypes.number,
    room: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    room_number: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    branch_name: PropTypes.string,
    priority: PropTypes.string,
    assigned_to: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    assigned_to_name: PropTypes.string,
  }),
  onSubmit: PropTypes.func.isRequired,
  submitting: PropTypes.bool,
};

export default CleaningTaskForm;
