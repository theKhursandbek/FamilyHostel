import { useState, useEffect, useCallback } from "react";
import { CheckCircle2 } from "lucide-react";
import { getTasks, assignTask, uploadImages, retryTask } from "../../services/cleaningService";
import { useToast } from "../../context/ToastContext";
import CleaningTaskCard from "../../components/CleaningTaskCard";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

function MyTasksPage() {
  const toast = useToast();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTasks({ mine: true });
      setTasks(data.results ?? data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const withAction = async (taskId, action) => {
    setActionLoading(taskId);
    try {
      await action();
      toast.success("Task updated");
      fetchTasks();
    } catch (err) {
      const detail = err.response?.data;
      toast.error(typeof detail === "string" ? detail : detail?.detail || "Action failed");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchTasks} />;

  const taskWord = tasks.length === 1 ? "task" : "tasks";
  const subtitle =
    tasks.length > 0
      ? `${tasks.length} ${taskWord} assigned to you`
      : "Your cleaning assignments appear here";

  return (
    <div className="staff-page">
      <header className="staff-hero">
        <h1 className="staff-hero__title">My Tasks</h1>
        <p className="staff-hero__sub">{subtitle}</p>
      </header>

      {tasks.length === 0 ? (
        <div className="staff-empty">
          <span className="staff-empty__icon" aria-hidden>
            <CheckCircle2 size={26} strokeWidth={1.6} />
          </span>
          <p className="staff-empty__title">Nothing to clean</p>
          <p className="staff-empty__sub">No tasks are assigned to you right now.</p>
        </div>
      ) : (
        tasks.map((task) => (
          <CleaningTaskCard
            key={task.id}
            task={task}
            isStaff
            isDirector={false}
            actionLoading={actionLoading}
            onAssign={(id) => withAction(id, () => assignTask(id))}
            onUpload={(id, items) => withAction(id, () => uploadImages(id, items))}
            onRetry={(id) => withAction(id, () => retryTask(id))}
            onOverride={() => {}}
            onViewDetail={() => {}}
          />
        ))
      )}
    </div>
  );
}

export default MyTasksPage;
