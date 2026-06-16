import { useCallback, useEffect, useRef, useState } from "react";

const THRESHOLD_PX = 65;   // how far the user must pull before refresh fires
const RESIST = 0.45;        // rubber-band resistance factor (< 1 = harder to pull)

/**
 * Pull-to-refresh for touch devices.
 *
 * Returns:
 *   - containerRef  → attach to the scrollable container element
 *   - pullDistance  → current overscroll distance in px (0–THRESHOLD_PX)
 *   - isPulling     → true while the user is actively dragging
 *   - isRefreshing  → true while onRefresh() promise is pending
 *
 * Usage:
 *   const { containerRef, pullDistance, isRefreshing } = usePullToRefresh(fetchData);
 *   <div ref={containerRef}> ... </div>
 *
 * Only fires when the container is scrolled to the top (scrollTop === 0).
 * Does NOT conflict with horizontal swipe on carousels (different axis guard).
 */
export default function usePullToRefresh(onRefresh) {
  const containerRef   = useRef(null);
  const startYRef      = useRef(null);
  const startXRef      = useRef(null);
  const axisLockedRef  = useRef(null); // "vertical" | "horizontal" | null
  const [pullDistance, setPullDistance] = useState(0);
  const [isPulling,    setIsPulling]    = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const onTouchStart = useCallback((e) => {
    const node = containerRef.current;
    // Only start if we are at the very top
    if (!node) return;
    const scrollTop = node === document.body ? window.scrollY : node.scrollTop;
    if (scrollTop > 0) return;
    startYRef.current = e.touches[0].clientY;
    startXRef.current = e.touches[0].clientX;
    axisLockedRef.current = null;
  }, []);

  const onTouchMove = useCallback((e) => {
    if (startYRef.current === null || isRefreshing) return;

    const dy = e.touches[0].clientY - startYRef.current;
    const dx = e.touches[0].clientX - startXRef.current;

    // Lock axis on first significant move
    if (!axisLockedRef.current) {
      if (Math.abs(dx) > Math.abs(dy) + 4) {
        axisLockedRef.current = "horizontal";
      } else if (dy > 4) {
        axisLockedRef.current = "vertical";
      } else {
        return;
      }
    }

    if (axisLockedRef.current !== "vertical") return;
    if (dy <= 0) return;

    // Prevent native scroll bounce while pulling
    e.preventDefault();
    const dist = Math.min(dy * RESIST, THRESHOLD_PX * 1.3);
    setIsPulling(true);
    setPullDistance(dist);
  }, [isRefreshing]);

  const onTouchEnd = useCallback(async () => {
    if (startYRef.current === null) return;
    startYRef.current = null;
    startXRef.current = null;
    axisLockedRef.current = null;
    setIsPulling(false);

    if (pullDistance >= THRESHOLD_PX) {
      setPullDistance(0);
      setIsRefreshing(true);
      try {
        await onRefresh();
      } finally {
        setIsRefreshing(false);
      }
    } else {
      setPullDistance(0);
    }
  }, [pullDistance, onRefresh]);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    node.addEventListener("touchstart", onTouchStart, { passive: true });
    node.addEventListener("touchmove",  onTouchMove,  { passive: false });
    node.addEventListener("touchend",   onTouchEnd,   { passive: true });
    return () => {
      node.removeEventListener("touchstart", onTouchStart);
      node.removeEventListener("touchmove",  onTouchMove);
      node.removeEventListener("touchend",   onTouchEnd);
    };
  }, [onTouchStart, onTouchMove, onTouchEnd]);

  return { containerRef, pullDistance, isPulling, isRefreshing };
}
