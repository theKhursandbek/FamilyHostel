import { useEffect, useState } from "react";
import PropTypes from "prop-types";
import Select from "./Select";
import { listBranches } from "../services/branchesService";
import { useAuth } from "../context/AuthContext";

/**
 * Branch scope selector for branch-restricted pages (Bookings, Cleaning…).
 *
 * Behavior:
 *   - SuperAdmin (CEO): renders a real `<select>` listing every branch.
 *     ``value`` may be empty until they pick one — parent should treat
 *     null as "no scope chosen yet" and gate the rest of the UI.
 *   - Director / Administrator / Staff: renders a read-only nameplate
 *     showing their pinned branch (no choice). The parent receives the
 *     pinned branch_id via ``onChange`` immediately on mount.
 *
 * Props:
 *   value     — currently selected branch id (number | string | null)
 *   onChange  — (branchId | null) => void
 *   className — optional wrapper class
 */
function BranchSelector({ value, onChange, className }) {
  const { user } = useAuth();
  const isSuperAdmin = user?.roles?.includes("superadmin") ?? false;

  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(false);

  // For non-SuperAdmin: pin to their own branch_id once on mount.
  useEffect(() => {
    if (isSuperAdmin) return;
    if (user?.branch_id && value !== user.branch_id) {
      onChange(user.branch_id);
    }
  }, [isSuperAdmin, user, value, onChange]);

  // For SuperAdmin: load full branch list.
  useEffect(() => {
    if (!isSuperAdmin) return;
    let cancelled = false;
    setLoading(true);
    listBranches()
      .then((data) => {
        if (cancelled) return;
        const list = Array.isArray(data) ? data : data?.results ?? [];
        setBranches(list);
      })
      .catch(() => {
        if (!cancelled) setBranches([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isSuperAdmin]);

  // Director / Admin / Staff — read-only nameplate
  if (!isSuperAdmin) {
    return (
      <div className={`branch-pin ${className || ""}`}>
        <span className="branch-pin__lbl">Branch</span>
        <span className="branch-pin__val">
          {user?.branch_name || "—"}
        </span>
      </div>
    );
  }

  // SuperAdmin — selectable
  return (
    <div className={`branch-picker ${className || ""}`}>
      <span className="branch-picker__lbl">Branch</span>
      <Select
        className="branch-picker__custom"
        value={value ?? ""}
        onChange={(v) => onChange(v ? Number(v) : null)}
        placeholder="— Select a branch —"
        loading={loading}
        options={branches.map((b) => ({ value: b.id, label: b.name }))}
      />
    </div>
  );
}

BranchSelector.propTypes = {
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onChange: PropTypes.func.isRequired,
  className: PropTypes.string,
};

export default BranchSelector;
