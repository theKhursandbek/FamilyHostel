import { useState, useEffect, useCallback } from "react";
import { getMyPenalties } from "../../services/staffService";
import Table from "../../components/Table";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";

const TYPE_LABELS = { late: "Late", absence: "Absence" };

const columns = [
  { key: "type", label: "Type", render: (val) => TYPE_LABELS[val] || val },
  { key: "count", label: "Count" },
  {
    key: "penalty_amount",
    label: "Amount",
    render: (val) => (val === null || val === undefined ? "—" : `${Number(val).toLocaleString()} сум`),
  },
  { key: "reason", label: "Reason", render: (val) => val || "—" },
  {
    key: "created_at",
    label: "Date",
    render: (val) => (val ? new Date(val).toLocaleDateString() : "—"),
  },
];

function PenaltiesViewPage() {
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

  if (loading) return <Loader />;
  if (error) return <ErrorMessage message={error} onRetry={fetchPenalties} />;

  return (
    <div>
      <div className="page-header"><h1>My Penalties</h1></div>
      <Table columns={columns} data={penalties} emptyMessage="No penalties" />
    </div>
  );
}

export default PenaltiesViewPage;
