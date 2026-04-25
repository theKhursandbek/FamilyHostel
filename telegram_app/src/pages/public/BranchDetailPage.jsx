import { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { getBranch, listRoomsByBranch } from "../../services/resources";
import { Loader, ErrorBox, Empty } from "../../components/Status";
import BackButton from "../../components/BackButton";

const STATUS_BADGE = {
  available: "badge-success",
  booked: "badge-warning",
  occupied: "badge-info",
  cleaning: "badge-muted",
  ready: "badge-success",
};

function BranchDetailPage() {
  const { id } = useParams();
  const [branch, setBranch] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [b, r] = await Promise.all([getBranch(id), listRoomsByBranch(id)]);
      setBranch(b);
      setRooms(r);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't load branch.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={fetchAll} />;

  return (
    <div>
      <BackButton to="/" />

      <h1>{branch?.name}</h1>
      <p className="text-hint">{branch?.location}</p>

      <h2 style={{ marginTop: 24 }}>Rooms</h2>

      {rooms.length === 0 ? (
        <Empty>No rooms listed for this branch.</Empty>
      ) : (
        rooms.map((room) => (
          <Link key={room.id} to={`/rooms/${room.id}`} className="card">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div className="card-title">Room {room.room_number}</div>
                <div className="card-subtitle">{room.room_type_name}</div>
              </div>
              <span className={`badge ${STATUS_BADGE[room.status] || "badge-muted"}`}>
                {room.status}
              </span>
            </div>
          </Link>
        ))
      )}
    </div>
  );
}

export default BranchDetailPage;
