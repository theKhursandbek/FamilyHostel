import { useEffect, useState, useCallback } from "react";
import { listMyBookings } from "../../services/resources";
import { Loader, ErrorBox, Empty } from "../../components/Status";

const STATUS_BADGE = {
  pending: "badge-warning",
  confirmed: "badge-info",
  paid: "badge-success",
  cancelled: "badge-muted",
  completed: "badge-success",
};

/**
 * Client area — list of the signed-in user's bookings.
 */
function MyBookingsPage() {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setBookings(await listMyBookings());
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't load bookings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={fetch} />;

  return (
    <div>
      <h1>My Bookings</h1>
      {bookings.length === 0 ? (
        <Empty>No bookings yet — pick a room to get started.</Empty>
      ) : (
        bookings.map((b) => (
          <div key={b.id} className="card">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div className="card-title">
                  Room {b.room_number || b.room?.room_number || `#${b.room}`}
                </div>
                <div className="card-subtitle">
                  {b.check_in} → {b.check_out}
                </div>
              </div>
              {b.status && (
                <span className={`badge ${STATUS_BADGE[b.status] || "badge-muted"}`}>
                  {b.status}
                </span>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default MyBookingsPage;
