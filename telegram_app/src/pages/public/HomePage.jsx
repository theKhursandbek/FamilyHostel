import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { listBranches } from "../../services/resources";
import { Loader, ErrorBox, Empty } from "../../components/Status";

/**
 * Public landing page.
 *
 * Shows the active branches as tappable cards. No authentication required —
 * prospective guests can explore the offering before signing in.
 */
function HomePage() {
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setBranches(await listBranches());
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't load branches.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={fetchAll} />;
  if (branches.length === 0) return <Empty>No branches available right now.</Empty>;

  return (
    <div>
      <h1>FamilyHostel</h1>
      <p className="text-hint">Choose a branch to explore rooms.</p>

      {branches.map((b) => (
        <Link key={b.id} to={`/branches/${b.id}`} className="card">
          <div className="card-title">{b.name}</div>
          <div className="card-subtitle">{b.location}</div>
        </Link>
      ))}
    </div>
  );
}

export default HomePage;
