import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import FilterBar from "../components/FilterBar";
import RoomCard from "../components/RoomCard";
import { listRooms } from "../services/catalogue";
import usePullToRefresh from "../hooks/usePullToRefresh";

/**
 * Catalogue page — landing route of the Mini App (§5.1).
 *
 * Renders a flat grid of available rooms across every branch, with sticky
 * filters and infinite scroll backed by cursor pagination (D17).
 */
function CataloguePage() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState({});
  const [rooms, setRooms] = useState([]);
  const [next, setNext] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const sentinelRef = useRef(null);

  // Pull-to-refresh: reset to first page and re-fetch.
  const handleRefresh = useCallback(async () => {
    const page = await listRooms({ filters });
    setRooms(page.results ?? []);
    setNext(page.next ?? null);
  }, [filters]);

  const { containerRef, pullDistance, isPulling, isRefreshing } = usePullToRefresh({
    onRefresh: handleRefresh,
  });

  // Fetch first page when the active filter set changes.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listRooms({ filters })
      .then((page) => {
        if (cancelled) return;
        setRooms(page.results ?? []);
        setNext(page.next ?? null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters]);

  // Infinite scroll — fetch the next cursor page when the sentinel becomes
  // visible. We bail out cleanly if the browser has no IntersectionObserver
  // (e.g. very old WebViews) and rely on the manual "Load more" button.
  const loadMore = useCallback(async () => {
    if (!next || loading) return;
    setLoading(true);
    try {
      const page = await listRooms({ cursorUrl: next });
      setRooms((current) => [...current, ...(page.results ?? [])]);
      setNext(page.next ?? null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [next, loading]);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return undefined;
    const node = sentinelRef.current;
    if (!node) return undefined;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) loadMore();
      },
      { rootMargin: "240px" }
    );
    io.observe(node);
    return () => io.disconnect();
  }, [loadMore]);

  return (
    <div className="catalogue-page" ref={containerRef}>
      {/* Pull-to-refresh indicator */}
      <div
        className="ptr-indicator"
        style={{ height: isPulling || isRefreshing ? Math.min(pullDistance * 0.6, 48) : 0 }}
        aria-hidden="true"
      >
        {isRefreshing
          ? <span className="ptr-indicator__spinner" />
          : isPulling
            ? <span className="ptr-indicator__arrow" style={{ transform: `rotate(${Math.min(pullDistance / 65, 1) * 180}deg)` }}>↓</span>
            : null}
      </div>
      <header className="catalogue-page__header">
        <h1>{t("catalogue.title", "Rooms")}</h1>
        <p className="catalogue-page__subtitle">
          {t("catalogue.subtitle", "Browse available rooms across all branches.")}
        </p>
      </header>

      <FilterBar value={filters} onApply={setFilters} />

      {error ? (
        <div className="catalogue-page__error" role="alert">
          {t("common.error", "Something went wrong.")}
        </div>
      ) : null}

      {!loading && rooms.length === 0 && !error ? (
        <div className="catalogue-page__empty">
          {t("catalogue.empty", "No rooms match these filters yet.")}
        </div>
      ) : null}

      <div className="room-grid">
        {rooms.map((room) => (
          <RoomCard key={room.id} room={room} />
        ))}
      </div>

      <div ref={sentinelRef} className="catalogue-page__sentinel" aria-hidden="true" />

      {next ? (
        <div className="catalogue-page__more">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={loadMore}
            disabled={loading}
          >
            {loading ? t("common.loading", "Loading…") : t("catalogue.load_more", "Load more")}
          </button>
        </div>
      ) : null}

      {loading && rooms.length === 0 ? (
        <div className="catalogue-page__loading">{t("common.loading", "Loading…")}</div>
      ) : null}
    </div>
  );
}

export default CataloguePage;
