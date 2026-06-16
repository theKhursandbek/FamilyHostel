import { useState, useEffect, useCallback } from "react";
import PropTypes from "prop-types";
import { CheckCircle2, CalendarDays, Banknote } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import {
  getTasks,
  assignTask,
  retryTask,
  uploadImages,
  overrideTask,
} from "../../services/cleaningService";
import {
  getTodayAttendance,
  checkIn,
  getDayOffRequests,
  getMyPenalties,
} from "../../services/staffService";
import { useSocket } from "../../hooks/useSocket";
import CleaningTaskCard from "../../components/CleaningTaskCard";
import Button from "../../components/Button";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

/**
 * Mobile-first home screen for Staff (cleaners / receptionists).
 *
 * Layout (top → bottom):
 *   1. Greeting + today's shift / check-in chip
 *   2. Hero "My Active Task" — the camera-first cleaning card
 *   3. Quick-stats row (active tasks · day-off · unpaid penalties)
 *   4. This week — completed count + pending requests at a glance
 *
 * Everything stays on the web/PWA shell; no Telegram.
 */

function greetingFor() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function asArray(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

function isThisWeek(value) {
  if (!value) return false;
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return false;
  return Date.now() - then <= 7 * 24 * 60 * 60 * 1000;
}

function formatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function ShiftChip({ today, onCheckIn, checkingIn }) {
  if (!today) return null;

  if (today.checked_in) {
    const tone = today.status === "late" ? "is-late" : "is-ok";
    return (
      <span className={`shift-chip ${tone}`}>
        <span className="shift-chip__dot" aria-hidden />
        <span>Checked in {formatTime(today.checked_in_at)}</span>
        {today.status === "late" && <span className="shift-chip__tag">Late</span>}
      </span>
    );
  }

  if (today.shift_type && today.branch) {
    return (
      <Button size="sm" onClick={onCheckIn} disabled={checkingIn}>
        {checkingIn ? "Checking in…" : `Check in · ${today.shift_type} shift`}
      </Button>
    );
  }

  return (
    <span className="shift-chip is-off">
      <span className="shift-chip__dot" aria-hidden />
      <span>No shift scheduled today</span>
    </span>
  );
}

ShiftChip.propTypes = {
  today: PropTypes.shape({
    checked_in: PropTypes.bool,
    checked_in_at: PropTypes.string,
    status: PropTypes.string,
    shift_type: PropTypes.string,
    branch: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    date: PropTypes.string,
  }),
  onCheckIn: PropTypes.func.isRequired,
  checkingIn: PropTypes.bool,
};

function StaffDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [tasks, setTasks] = useState([]);
  const [daysOff, setDaysOff] = useState([]);
  const [penalties, setPenalties] = useState([]);
  const [today, setToday] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(null);
  const [checkingIn, setCheckingIn] = useState(false);

  const fetchAll = useCallback(async () => {
    setError("");
    try {
      const [taskRes, daysOffRes, penaltiesRes, todayRes] =
        await Promise.allSettled([
          getTasks({ mine: true }),
          getDayOffRequests(),
          getMyPenalties(),
          getTodayAttendance(),
        ]);
      if (taskRes.status === "fulfilled") setTasks(asArray(taskRes.value));
      if (daysOffRes.status === "fulfilled") setDaysOff(asArray(daysOffRes.value));
      if (penaltiesRes.status === "fulfilled")
        setPenalties(asArray(penaltiesRes.value));
      if (todayRes.status === "fulfilled") setToday(todayRes.value);

      const allFailed =
        taskRes.status === "rejected" &&
        daysOffRes.status === "rejected" &&
        penaltiesRes.status === "rejected";
      if (allFailed) {
        setError(
          taskRes.reason?.response?.data?.detail || "Failed to load dashboard."
        );
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useSocket("staff", {
    cleaning_task_updated: () => fetchAll(),
    penalty_created: () => fetchAll(),
    day_off_request_updated: () => fetchAll(),
  });

  const withAction = useCallback(
    async (taskId, fn) => {
      setActionLoading(taskId);
      try {
        await fn();
        await fetchAll();
      } finally {
        setActionLoading(null);
      }
    },
    [fetchAll]
  );

  const handleAssign = (id) => withAction(id, () => assignTask(id));
  const handleRetry = (id) => withAction(id, () => retryTask(id));
  const handleUpload = (id, items) => withAction(id, () => uploadImages(id, items));
  const handleOverride = (id, reason) =>
    withAction(id, () => overrideTask(id, reason));
  const handleViewDetail = () => navigate("/staff/my-tasks");

  const handleCheckIn = async () => {
    if (!today?.branch || !today?.shift_type) return;
    setCheckingIn(true);
    try {
      await checkIn({
        branch: today.branch,
        date: today.date,
        shift_type: today.shift_type,
      });
      await fetchAll();
    } finally {
      setCheckingIn(false);
    }
  };

  if (loading) return <Loader message="Loading your day…" />;
  if (error) return <ErrorMessage message={error} onRetry={fetchAll} />;

  const activeTasks = tasks.filter((t) => t.status !== "completed");
  const heroTask = activeTasks[0] || null;
  const pendingDaysOff = daysOff.filter((r) => r.status === "pending");
  const unpaidPenalties = penalties.filter((p) => !p.is_paid);
  const unpaidTotal = unpaidPenalties.reduce(
    (sum, p) => sum + Number(p.amount || 0),
    0
  );
  const completedThisWeek = tasks.filter(
    (t) => t.status === "completed" && isThisWeek(t.completed_at || t.updated_at)
  ).length;

  const displayName = user?.full_name?.trim() || user?.phone || "there";

  return (
    <div className="staff-home">
      <header className="staff-home__greet">
        <div>
          <p className="staff-home__hello">{greetingFor()},</p>
          <h1 className="staff-home__name">{displayName}</h1>
        </div>
        <ShiftChip today={today} onCheckIn={handleCheckIn} checkingIn={checkingIn} />
      </header>

      <section className="staff-home__hero">
        <div className="staff-home__hero-head">
          <h2 className="section-title">My Active Task</h2>
          {activeTasks.length > 1 && (
            <button
              type="button"
              className="link-btn"
              onClick={() => navigate("/staff/my-tasks")}
            >
              {activeTasks.length} tasks →
            </button>
          )}
        </div>

        {heroTask ? (
          <CleaningTaskCard
            task={heroTask}
            isStaff
            onAssign={handleAssign}
            onUpload={handleUpload}
            onRetry={handleRetry}
            onOverride={handleOverride}
            onViewDetail={handleViewDetail}
            actionLoading={actionLoading}
          />
        ) : (
          <div className="staff-empty">
            <span className="staff-empty__icon" aria-hidden>
              <CheckCircle2 size={26} strokeWidth={1.6} />
            </span>
            <p className="staff-empty__title">You&apos;re all caught up</p>
            <p className="staff-empty__sub">
              No active cleaning tasks right now. Nice work!
            </p>
          </div>
        )}
      </section>

      <section className="staff-stats">
        <div className="staff-stat">
          <span className="staff-stat__num">{activeTasks.length}</span>
          <span className="staff-stat__lbl">Active tasks</span>
        </div>
        <div className="staff-stat">
          <span className="staff-stat__num">{pendingDaysOff.length}</span>
          <span className="staff-stat__lbl">Day-off pending</span>
        </div>
        <div className="staff-stat">
          <span className="staff-stat__num staff-stat__num--warn">
            {unpaidPenalties.length}
          </span>
          <span className="staff-stat__lbl">Unpaid penalties</span>
        </div>
      </section>

      <section className="section">
        <h3 className="section-title">This week</h3>
        <ul className="staff-week">
          <li className="staff-week__row">
            <span className="staff-week__ico" aria-hidden>
              <CheckCircle2 size={18} strokeWidth={1.8} />
            </span>
            <span className="staff-week__txt">Rooms cleaned</span>
            <span className="staff-week__val">{completedThisWeek}</span>
          </li>
          <li className="staff-week__row">
            <span className="staff-week__ico" aria-hidden>
              <CalendarDays size={18} strokeWidth={1.8} />
            </span>
            <span className="staff-week__txt">Day-off requests</span>
            <button
              type="button"
              className="staff-week__val link-btn"
              onClick={() => navigate("/staff/days-off")}
            >
              {pendingDaysOff.length} pending →
            </button>
          </li>
          <li className="staff-week__row">
            <span className="staff-week__ico" aria-hidden>
              <Banknote size={18} strokeWidth={1.8} />
            </span>
            <span className="staff-week__txt">Unpaid penalties</span>
            <button
              type="button"
              className="staff-week__val link-btn"
              onClick={() => navigate("/staff/penalties")}
            >
              {unpaidTotal.toLocaleString()} UZS →
            </button>
          </li>
        </ul>
      </section>
    </div>
  );
}

export default StaffDashboard;
