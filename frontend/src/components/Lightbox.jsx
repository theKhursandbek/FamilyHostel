import { useEffect, useState, useCallback } from "react";
import PropTypes from "prop-types";
import { ChevronLeft, ChevronRight, X } from "lucide-react";

/**
 * Fullscreen image lightbox.
 *
 * Props:
 *  - images: [{url, alt?}] (or strings)
 *  - startIndex: which image to open first
 *  - onClose: () => void
 */
function normalize(images) {
  return (images || [])
    .map((it, i) => {
      if (!it) return null;
      if (typeof it === "string") return { id: i, url: it };
      const url = it.url || it.image || it.image_url || it.src;
      if (!url) return null;
      return { id: it.id ?? i, url, alt: it.alt };
    })
    .filter(Boolean);
}

function Lightbox({ images, startIndex = 0, onClose, caption }) {
  const slides = normalize(images);
  const total = slides.length;
  const [index, setIndex] = useState(Math.min(startIndex, Math.max(0, total - 1)));

  const prev = useCallback(
    (e) => { e?.stopPropagation?.(); setIndex((i) => (i - 1 + total) % total); },
    [total],
  );
  const next = useCallback(
    (e) => { e?.stopPropagation?.(); setIndex((i) => (i + 1) % total); },
    [total],
  );

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft" && total > 1) prev();
      else if (e.key === "ArrowRight" && total > 1) next();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose, prev, next, total]);

  if (total === 0) return null;
  const current = slides[index];

  return (
    <div
      className="lightbox"
      aria-label="Image viewer"
    >
      <button
        type="button"
        className="lightbox__backdrop"
        onClick={onClose}
        aria-label="Close viewer"
      />

      <button
        type="button"
        className="lightbox__close"
        onClick={onClose}
        aria-label="Close"
      >
        <X size={22} />
      </button>

      {total > 1 && (
        <button
          type="button"
          className="lightbox__nav lightbox__nav--prev"
          onClick={prev}
          aria-label="Previous image"
        >
          <ChevronLeft size={26} />
        </button>
      )}

      <img
        src={current.url}
        alt={current.alt || `Image ${index + 1}`}
        className="lightbox__image"
      />

      {total > 1 && (
        <button
          type="button"
          className="lightbox__nav lightbox__nav--next"
          onClick={next}
          aria-label="Next image"
        >
          <ChevronRight size={26} />
        </button>
      )}

      <div className="lightbox__caption">
        {caption && <span className="lightbox__title">{caption}</span>}
        {total > 1 && (
          <span className="lightbox__counter">{index + 1} / {total}</span>
        )}
      </div>
    </div>
  );
}

Lightbox.propTypes = {
  images: PropTypes.array.isRequired,
  startIndex: PropTypes.number,
  onClose: PropTypes.func.isRequired,
  caption: PropTypes.string,
};

export default Lightbox;
