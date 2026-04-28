import { useState, useEffect, useCallback, useMemo } from "react";
import {
  getAvailableWorkbooks,
  downloadBranchWorkbook,
  downloadGeneralManagerWorkbook,
  saveBlob,
  getBranchDashboard,
} from "../../services/reportService";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import usePersistedBranch from "../../hooks/usePersistedBranch";
import BranchSelector from "../../components/BranchSelector";
import Button from "../../components/Button";
import Select from "../../components/Select";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";
import BranchDashboard from "./components/BranchDashboard";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/**
 * Reports — REFACTOR_PLAN_2026_04 §4.
 *
 * Non-CEO: pinned to own branch · in-page dashboard + sticky download.
 * CEO: branch picker → dashboard + per-branch download + per-GM workbook (Q7).
 */
function ReportsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const today = new Date();
  const isCeo = (user?.roles || []).includes("superadmin");

  const [branchId, setBranchId] = usePersistedBranch(
    "branchScope:reports",
    isCeo,
    user?.branch_id ?? null,
  );
  const [year, setYear] = useState(String(today.getFullYear()));
  const [month, setMonth] = useState(String(today.getMonth() + 1));

  const [dashboard, setDashboard] = useState(null);
  const [dashLoading, setDashLoading] = useState(false);
  const [dashError, setDashError] = useState(null);

  const [items, setItems] = useState([]);
  const [downloadingKey, setDownloadingKey] = useState(null);

  const ceoMustPick = isCeo && !branchId;

  const loadDashboard = useCallback(async () => {
    if (!branchId) {
      setDashboard(null);
      return;
    }
    try {
      setDashLoading(true);
      setDashError(null);
      const data = await getBranchDashboard({
        branchId, year: Number(year), month: Number(month),
      });
      setDashboard(data);
    } catch (err) {
      setDashError(err.response?.data?.detail || "Failed to load dashboard");
    } finally {
      setDashLoading(false);
    }
  }, [branchId, year, month]);

  const loadWorkbooks = useCallback(async () => {
    try {
      const data = await getAvailableWorkbooks();
      setItems(data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to load workbook list");
    }
  }, [toast]);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);
  useEffect(() => { loadWorkbooks(); }, [loadWorkbooks]);

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

  const handleDownloadGm = async (item) => {
    const key = `gm-${item.director_id}-${item.year}`;
    try {
      setDownloadingKey(key);
      const response = await downloadGeneralManagerWorkbook(
        item.director_id, item.year,
      );
      const safe = (item.director_name || `director_${item.director_id}`)
        .replaceAll(/\s+/g, "_");
      saveBlob(response, `gm_${safe}_${item.year}.xlsx`);
      toast.success("GM workbook downloaded");
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

  const gmItems = useMemo(
    () => items.filter(
      (i) => i.kind === "general_manager" && String(i.year) === String(year),
    ),
    [items, year],
  );

  return (
    <div>
      <div className="page-header">
        <h1>Reports</h1>
        {isCeo && <BranchSelector value={branchId} onChange={setBranchId} />}
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
          {gmItems.map((item) => {
            const key = `gm-${item.director_id}-${item.year}`;
            return (
              <Button
                key={key}
                variant="secondary"
                onClick={() => handleDownloadGm(item)}
                disabled={downloadingKey === key}
              >
                {downloadingKey === key
                  ? "Generating…"
                  : `Download ${item.director_name}'s GM workbook`}
              </Button>
            );
          })}
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

      {!ceoMustPick && dashLoading && <Loader />}

      {!ceoMustPick && !dashLoading && !dashError && (
        <BranchDashboard data={dashboard} />
      )}
    </div>
  );
}

export default ReportsPage;
