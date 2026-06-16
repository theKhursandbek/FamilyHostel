import { useState, useEffect, useCallback } from "react";
import { LogOut, CheckCircle2 } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { getMyPenalties } from "../../services/staffService";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const TYPE_LABELS = { late: "Late", absence: "Absence" };
const TYPE_TONE = { late: "staff-badge--warning", absence: "staff-badge--danger" };

function initialsOf(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "•";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts.at(-1)[0]).toUpperCase();
}

function fmtAmount(val) {
  if (val === null || val === undefined || val === "") return "—";
  const n = Number(val);
  if (Number.isNaN(n)) return String(val);
  return `${n.toLocaleString()} сум`;
}

function fmtDate(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/**
 * “Me” page — the staff analogue of the Telegram Mini App's Profile tab.
 *
 * Profile hero (avatar + name + phone) → personal penalties record → sign-out.
 * Sign-out lives here (not in a top bar) exactly like telegram_app.
 */
function PenaltiesViewPage() {
  const { user, logout } = useAuth();
  const [penalties, setPenalties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPenalties = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMyPenalties();
      setPenalties(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load penalties");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPenalties();
  }, [fetchPenalties]);

  const fullName = user?.full_name?.trim() || user?.phone || "Staff";
  const total = penalties.reduce((sum, p) => sum + Number(p.penalty_amount || 0), 0);
  const recordWord = penalties.length === 1 ? "record" : "records";

  function renderPenalties() {
    if (loading) return <Loader />;
    if (error) return <ErrorMessage message={error} onRetry={fetchPenalties} />;
    if (penalties.length === 0) {
      return (
        <div className="staff-empty">
          <span className="staff-empty__icon" aria-hidden>
            <CheckCircle2 size={26} strokeWidth={1.6} />
          </span>
          <p className="staff-empty__title">A clean record</p>
          <p className="staff-empty__sub">You have no penalties. Keep it up!</p>
        </div>
      );
    }
    return (
      <>
        <p className="staff-section-sub">
          {total.toLocaleString()} сум across {penalties.length} {recordWord}
        </p>
        <ul className="staff-stack">
          {penalties.map((p, i) => (
            <li key={p.id ?? i} className="staff-rec">
              <div className="staff-rec__top">
                <span className="staff-rec__title">
                  <span className={`staff-badge ${TYPE_TONE[p.type] || ""}`}>
                    {TYPE_LABELS[p.type] || p.type}
                  </span>
                  {p.count > 1 ? ` ×${p.count}` : ""}
                </span>
                <span className="staff-rec__amount">{fmtAmount(p.penalty_amount)}</span>
              </div>
              <p className="staff-rec__meta">
                {fmtDate(p.created_at)}
                {p.reason ? ` · ${p.reason}` : ""}
              </p>
            </li>
          ))}
        </ul>
      </>
    );
  }

  return (
    <div className="staff-page">
      <header className="staff-profile">
        <div className="staff-profile__avatar" aria-hidden>{initialsOf(fullName)}</div>
        <h1 className="staff-profile__name">{fullName}</h1>
        {user?.phone && <p className="staff-profile__sub">{user.phone}</p>}
      </header>

      <h2 className="staff-section-title">My penalties</h2>
      {renderPenalties()}

      <button type="button" className="staff-profile__logout" onClick={logout}>
        <LogOut size={16} strokeWidth={1.8} aria-hidden />
        Sign out
      </button>
    </div>
  );
}

export default PenaltiesViewPage;
