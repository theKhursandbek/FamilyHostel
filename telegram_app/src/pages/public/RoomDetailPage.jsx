import { useEffect, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getRoom } from "../../services/resources";
import { Loader, ErrorBox } from "../../components/Status";
import BackButton from "../../components/BackButton";
import { useAuth } from "../../context/AuthContext";
import { useTelegram } from "../../context/TelegramContext";

function RoomDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();
  const { hapticImpact } = useTelegram();

  const [room, setRoom] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [imgIdx, setImgIdx] = useState(0);

  const fetchRoom = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRoom(await getRoom(id));
      setImgIdx(0);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't load room.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchRoom();
  }, [fetchRoom]);

  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={fetchRoom} />;
  if (!room) return null;

  const images = room.images || [];
  const currentImg = images[imgIdx]?.image_url;
  const isClient = user?.roles?.includes("client");

  const handleBook = () => {
    hapticImpact("medium");
    if (!isAuthenticated) {
      navigate("/login");
    } else if (isClient) {
      // Real booking creation flow lives in the admin/web app for now;
      // the mini app navigates clients to their bookings list as feedback.
      navigate("/me/bookings");
    } else {
      // Logged in as staff/admin via dev fallback — booking is a client action.
      navigate("/me");
    }
  };

  return (
    <div>
      <BackButton />

      {currentImg ? (
        <div className="media-card">
          <img src={currentImg} alt={`Room ${room.room_number}`} className="media-img" />
          {images.length > 1 && (
            <div
              style={{
                display: "flex",
                gap: 6,
                justifyContent: "center",
                padding: "8px 0",
              }}
            >
              {images.map((img, i) => (
                <button
                  key={img.id}
                  type="button"
                  aria-label={`Show image ${i + 1}`}
                  onClick={() => setImgIdx(i)}
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 4,
                    border: "none",
                    background: i === imgIdx ? "var(--tg-button)" : "rgba(0,0,0,0.2)",
                    cursor: "pointer",
                  }}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="media-card">
          <div
            className="media-img"
            style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
          >
            <span className="text-hint">No photos yet</span>
          </div>
        </div>
      )}

      <h1>Room {room.room_number}</h1>
      <p className="text-hint">
        {room.room_type_name} · {room.branch_name}
      </p>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title">Status</div>
        <div className="card-subtitle">
          {room.status === "available"
            ? "Ready to book — tap below to continue."
            : `Currently ${room.status}.`}
        </div>
      </div>

      <button
        type="button"
        className="btn"
        style={{ marginTop: 16 }}
        disabled={room.status !== "available"}
        onClick={handleBook}
      >
        {isAuthenticated ? "Book this room" : "Sign in to book"}
      </button>
    </div>
  );
}

export default RoomDetailPage;
