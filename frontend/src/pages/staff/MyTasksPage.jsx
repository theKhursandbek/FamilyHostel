import { useState, useEffect, useCallback } from "react";
import { getTasks } from "../../services/cleaningService";
import CleaningTaskCard from "../../components/CleaningTaskCard";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";
import { assignTask, completeTask, uploadImages, retryTask } from "../../services/cleaningService";

function MyTasksPage() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTasks({ assigned_to_me: true });
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
      fetchTasks();
    } catch (err) {
      const detail = err.response?.data;
      alert(typeof detail === "string" ? detail : detail?.detail || "Action failed");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchTasks} />;

  return (
    <div>
      <h1 style={{ marginBottom: 20 }}>My Tasks</h1>
      {tasks.length === 0 ? (
        <p style={{ color: "#9ca3af", textAlign: "center", padding: 40 }}>No tasks assigned to you.</p>
      ) : (
        tasks.map((task) => (
          <CleaningTaskCard
            key={task.id}
            task={task}
            isDirector={false}
            actionLoading={actionLoading}
            onAssign={(id) => withAction(id, () => assignTask(id))}
            onComplete={(id) => withAction(id, () => completeTask(id))}
            onUpload={(id, files) => withAction(id, () => uploadImages(id, files))}
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
