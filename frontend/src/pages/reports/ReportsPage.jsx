import { useState, useEffect, useCallback, useMemo } from "react";
import {
  downloadBranchWorkbook,
  saveBlob,
  getBranchDashboard,
} from "../../services/reportService";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useBranchScope } from "../../context/BranchScopeContext";
import usePersistedBranch from "../../hooks/usePersistedBranch";
import Button from "../../components/Button";
import Select from "../../components/Select";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";
import BranchDashboard from "./components/BranchDashboard";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// Survives React Router navigation so the dashboard stays visible immediately
// on revisit instead of showing a loader while fresh data arrives.
const _dashCache = new Map();

/**
 * Reports — REFACTOR_PLAN_2026_04 §4.
 *
 * Non-CEO: pinned to own branch · in-page dashboard + sticky download.
 * CEO: branch picker → dashboard + per-branch download.
 */
function ReportsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const today = new Date();
  const isCeo = (user?.roles || []).includes("superadmin");
  const isDirector = (user?.roles || []).includes("director");
  const canEdit = isCeo || isDirector;

  const [branchId, setBranchId] = usePersistedBranch(
    "branchScope:reports",
    isCeo,
    user?.branch_id ?? null,
  );

  // Register branch scope in global fixed header
  const { register, unregister } = useBranchScope();
  useEffect(() => { register(branchId, setBranchId); }, [branchId, register, setBranchId]);
  useEffect(() => () => unregister(), [unregister]);

  const [year, setYear] = useState(String(today.getFullYear()));
  const [month, setMonth] = useState(String(today.getMonth() + 1));

  const isCurrentMonth =
    Number(year) === today.getFullYear() && Number(month) === today.getMonth() + 1;

  const [dashboard, setDashboard] = useState(() => {
    const key = branchId ? `${branchId}|${year}|${month}` : null;
    return key ? (_dashCache.get(key) ?? null) : null;
  });
  const [dashLoading, setDashLoading] = useState(false);
  const [dashError, setDashError] = useState(null);

  const [downloadingKey, setDownloadingKey] = useState(null);

  const ceoMustPick = isCeo && !branchId;

  const loadDashboard = useCallback(async () => {
    if (!branchId) {
      setDashboard(null);
      return;
    }
    const key = `${branchId}|${year}|${month}`;
    const cached = _dashCache.get(key);
    if (cached) setDashboard(cached);
    try {
      setDashLoading(true);
      setDashError(null);
      const data = await getBranchDashboard({
        branchId, year: Number(year), month: Number(month),
      });
      _dashCache.set(key, data);
      setDashboard(data);
    } catch (err) {
      setDashError(err.response?.data?.detail || "Failed to load dashboard");
    } finally {
      setDashLoading(false);
    }
  }, [branchId, year, month]);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);

  const handleDownloadBranch = async () => {
    if (!branchId) return;
    const key = `branch-${branchId}-${year}`;
    try {
      setDownloadingKey(key);
      const response = await downloadBranchWorkbook(branchId, Number(year));
      saveBlob(response, `branch_${branchId}_${year}.xlsx`);
      toast.success("Workbook downloaded");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Download failed");
    } finally {
      setDownloadingKey(null);
    }
  };

  const yearOptions = useMemo(() => {
    const cur = today.getFullYear();
    return [cur - 1, cur, cur + 1].map((y) => ({
      value: String(y), label: String(y),
    }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>Reports</h1>
      </div>

      <div
        className="card"
        style={{
          display: "flex", gap: 12, alignItems: "flex-end",
          marginBottom: 16, flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 140 }}>
          <label className="label" htmlFor="rep-year">Year</label>
          <Select
            id="rep-year" value={year} onChange={(v) => setYear(v)}
            options={yearOptions}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <label className="label" htmlFor="rep-month">Month</label>
          <Select
            id="rep-month" value={month} onChange={(v) => setMonth(v)}
            options={MONTHS.map((n, i) => ({
              value: String(i + 1), label: n,
            }))}
          />
        </div>
        <div
          style={{
            marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap",
          }}
        >
          {branchId && (
            <Button
              onClick={handleDownloadBranch}
              disabled={downloadingKey === `branch-${branchId}-${year}`}
            >
              {downloadingKey === `branch-${branchId}-${year}`
                ? "Generating…"
                : `Download branch workbook (${year})`}
            </Button>
          )}
        </div>
      </div>

      {ceoMustPick && (
        <div className="branch-empty">
          <p className="branch-empty__title">Select a branch to begin</p>
          <p className="branch-empty__hint">
            CEO can pick any branch above to load its dashboard.
          </p>
        </div>
      )}

      {!ceoMustPick && dashError && (
        <ErrorMessage message={dashError} onRetry={loadDashboard} />
      )}

      {!ceoMustPick && dashLoading && !dashboard && <Loader />}

      {!ceoMustPick && !dashError && dashboard && (
        <div style={{ opacity: dashLoading ? 0.5 : 1, transition: "opacity 0.25s" }}>
          <BranchDashboard
            data={dashboard}
            branchId={branchId}
            year={Number(year)}
            month={Number(month)}
            canAddAdjustment={canEdit && isCurrentMonth}
            onRefresh={loadDashboard}
          />
        </div>
      )}
    </div>
  );
}

export default ReportsPage;
