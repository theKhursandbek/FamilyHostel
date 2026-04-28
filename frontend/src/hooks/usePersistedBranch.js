import { useEffect, useState } from "react";

/**
 * Persists a SuperAdmin's chosen branch across navigations / remounts.
 *
 * Director / Admin / Staff are pinned to their own branch (passed as the
 * `fallback` argument) and the storage layer is bypassed entirely.
 *
 * Usage:
 *   const [branchId, setBranchId] = usePersistedBranch(
 *     "branchScope:bookings",
 *     isSuperAdmin,
 *     user?.branch_id ?? null,
 *   );
 */
function usePersistedBranch(storageKey, isSuperAdmin, fallback) {
  const [branchId, setBranchId] = useState(() => {
    if (!isSuperAdmin) return fallback;
    try {
      const raw = sessionStorage.getItem(storageKey);
      return raw ? Number(raw) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    if (!isSuperAdmin) return;
    try {
      if (branchId == null || branchId === "") {
        sessionStorage.removeItem(storageKey);
      } else {
        sessionStorage.setItem(storageKey, String(branchId));
      }
    } catch {
      /* sessionStorage may be unavailable (e.g. private mode) — silently ignore. */
    }
  }, [storageKey, isSuperAdmin, branchId]);

  return [branchId, setBranchId];
}

export default usePersistedBranch;
