import { useCallback, useEffect, useRef, useState } from "react";
import { X, ChevronLeft, ChevronRight, Expand } from "lucide-react";

/**
 * Room image carousel — touch + keyboard friendly, mirrors the website's
 * Lightbox behaviour for design parity (plan §1.5, §5.2).
 *
 * Props:
 *   images:  Array<{ id, image_url }>
 *   alt:     string used as the alt prefix for each slide
 */
function RoomCarousel({ images = [], alt = "Room" }) {
  const [index, setIndex] = useState(0);
  const [lightbox, setLightbox] = useState(false);
  const [lbIndex, setLbIndex] = useState(0);
  const trackRef = useRef(null);
  const startX = useRef(null);

  const safeImages = images.filter(Boolean);
  const total = safeImages.length;

  const goTo = useCallback(
    (next) => {
      if (total === 0) return;
      const wrapped = ((next % total) + total) % total;
      setIndex(wrapped);
    },
    [total]
  );

  const onPrev = useCallback(() => goTo(index - 1), [goTo, index]);
  const onNext = useCallback(() => goTo(index + 1), [goTo, index]);

  // Keyboard support for desktop preview / accessibility.
  useEffect(() => {
    const handler = (e) => {
      if (lightbox) {
        if (e.key === "ArrowLeft")  setLbIndex((i) => ((i - 1 + total) % total));
        if (e.key === "ArrowRight") setLbIndex((i) => ((i + 1) % total));
        if (e.key === "Escape")     setLightbox(false);
      } else {
        if (e.key === "ArrowLeft") onPrev();
        if (e.key === "ArrowRight") onNext();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onPrev, onNext, lightbox, total]);

  const openLightbox = useCallback((i) => {
    setLbIndex(i);
    setLightbox(true);
  }, []);

  // Lightbox touch swipe
  const lbStartX = useRef(null);
  const onLbTouchStart = (e) => { lbStartX.current = e.touches[0].clientX; };
  const onLbTouchEnd = (e) => {
    if (lbStartX.current == null) return;
    const dx = e.changedTouches[0].clientX - lbStartX.current;
    if (Math.abs(dx) > 40) {
      setLbIndex((i) => dx > 0 ? ((i - 1 + total) % total) : ((i + 1) % total));
    }
    lbStartX.current = null;
  };

  // Touch swipe — stop propagation so Telegram's swipe-down-to-close doesn't
  // hijack horizontal gestures (R9).
  const onTouchStart = (e) => {
    startX.current = e.touches[0].clientX;
  };
  const onTouchEnd = (e) => {
    if (startX.current == null) return;
    const dx = e.changedTouches[0].clientX - startX.current;
    if (Math.abs(dx) > 40) {
      if (dx > 0) onPrev();
      else onNext();
      e.stopPropagation();
    }
    startX.current = null;
  };

  if (total === 0) {
    return (
      <div className="room-carousel room-carousel--empty">
        <div className="room-carousel__placeholder">🏨</div>
      </div>
    );
  }

  return (
    <div
      className="room-carousel"
      ref={trackRef}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      <div
        className="room-carousel__track"
        style={{ transform: `translateX(-${index * 100}%)` }}
      >
        {safeImages.map((img, i) => (
          <div className="room-carousel__slide" key={img.id ?? i}>
            <img
              src={img.image_url}
              alt={`${alt} (${i + 1}/${total})`}
              loading="lazy"
              onClick={() => openLightbox(i)}
              style={{ cursor: "zoom-in" }}
            />
          </div>
        ))}
      </div>

      {/* Expand button — bottom-right corner */}
      <button
        type="button"
        className="room-carousel__expand"
        onClick={() => openLightbox(index)}
        aria-label="View full image"
      >
        <Expand size={16} strokeWidth={2} />
      </button>

      {total > 1 ? (
        <>
          <button
            type="button"
            className="room-carousel__nav room-carousel__nav--prev"
            onClick={onPrev}
            aria-label="Previous image"
          >
            ‹
          </button>
          <button
            type="button"
            className="room-carousel__nav room-carousel__nav--next"
            onClick={onNext}
            aria-label="Next image"
          >
            ›
          </button>
          <div className="room-carousel__dots" role="tablist">
            {safeImages.map((img, i) => (
              <button
                key={img.id ?? i}
                type="button"
                role="tab"
                aria-selected={i === index}
                aria-label={`Image ${i + 1}`}
                className={`room-carousel__dot ${i === index ? "is-active" : ""}`}
                onClick={() => goTo(i)}
              />
            ))}
          </div>
        </>
      ) : null}

      {/* Lightbox overlay */}
      {lightbox ? (
        <div
          className="room-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label="Full image view"
          onTouchStart={onLbTouchStart}
          onTouchEnd={onLbTouchEnd}
        >
          <button
            type="button"
            className="room-lightbox__close"
            onClick={() => setLightbox(false)}
            aria-label="Close"
          >
            <X size={22} strokeWidth={2} />
          </button>

          <div className="room-lightbox__img-wrap">
            <img
              src={safeImages[lbIndex]?.image_url}
              alt={`${alt} (${lbIndex + 1}/${total})`}
              className="room-lightbox__img"
            />
          </div>

          {total > 1 ? (
            <>
              <button
                type="button"
                className="room-lightbox__nav room-lightbox__nav--prev"
                onClick={() => setLbIndex((i) => ((i - 1 + total) % total))}
                aria-label="Previous image"
              >
                <ChevronLeft size={28} strokeWidth={2} />
              </button>
              <button
                type="button"
                className="room-lightbox__nav room-lightbox__nav--next"
                onClick={() => setLbIndex((i) => ((i + 1) % total))}
                aria-label="Next image"
              >
                <ChevronRight size={28} strokeWidth={2} />
              </button>
              <div className="room-lightbox__counter">
                {lbIndex + 1} / {total}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default RoomCarousel;
