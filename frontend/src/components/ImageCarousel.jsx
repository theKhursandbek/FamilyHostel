import { useState, useEffect, useCallback } from "react";
import PropTypes from "prop-types";
import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Lightweight image carousel.
 *
 * Props:
 *  - images: array of { id?, url, alt? } OR array of strings (urls)
 *  - aspectRatio: CSS aspect-ratio (default "16 / 10")
 *  - showThumbnails: bool (default true if more than 1 image)
 *  - emptyLabel: string shown when no images
 */
function normalize(images) {
  return (images || [])
    .map((it, i) => {
      if (!it) return null;
      if (typeof it === "string") return { id: i, url: it };
      const url = it.url || it.image_url || it.src;
      if (!url) return null;
      return { id: it.id ?? i, url, alt: it.alt };
    })
    .filter(Boolean);
}

function ImageCarousel({
  images,
  aspectRatio = "16 / 10",
  showThumbnails,
  emptyLabel = "No images",
  rounded = true,
}) {
  const slides = normalize(images);
  const total = slides.length;
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (index >= total) setIndex(0);
  }, [index, total]);

  const goPrev = useCallback(
    (e) => {
      e?.stopPropagation();
      setIndex((i) => (i - 1 + total) % total);
    },
    [total],
  );
  const goNext = useCallback(
    (e) => {
      e?.stopPropagation();
      setIndex((i) => (i + 1) % total);
    },
    [total],
  );

  if (total === 0) {
    return (
      <div
        className={`carousel ${rounded ? "carousel--rounded" : ""}`}
        style={{ aspectRatio }}
      >
        <div className="carousel__empty">{emptyLabel}</div>
      </div>
    );
  }

  const showThumbs = showThumbnails ?? total > 1;
  const current = slides[index];

  return (
    <div className={`carousel ${rounded ? "carousel--rounded" : ""}`}>
      <div className="carousel__viewport" style={{ aspectRatio }}>
        <img
          key={current.id}
          src={current.url}
          alt={current.alt || `Slide ${index + 1}`}
          className="carousel__image"
        />

        {total > 1 && (
          <>
            <button
              type="button"
              className="carousel__nav carousel__nav--prev"
              onClick={goPrev}
              aria-label="Previous image"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              type="button"
              className="carousel__nav carousel__nav--next"
              onClick={goNext}
              aria-label="Next image"
            >
              <ChevronRight size={18} />
            </button>

            <div className="carousel__counter">
              {index + 1} / {total}
            </div>

            <div className="carousel__dots">
              {slides.map((s, i) => (
                <button
                  key={s.id}
                  type="button"
                  className={`carousel__dot ${i === index ? "is-active" : ""}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setIndex(i);
                  }}
                  aria-label={`Go to image ${i + 1}`}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {showThumbs && (
        <div className="carousel__thumbs">
          {slides.map((s, i) => (
            <button
              key={s.id}
              type="button"
              className={`carousel__thumb ${i === index ? "is-active" : ""}`}
              onClick={() => setIndex(i)}
              aria-label={`Show image ${i + 1}`}
            >
              <img src={s.url} alt={s.alt || `Thumbnail ${i + 1}`} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default ImageCarousel;

ImageCarousel.propTypes = {
  images: PropTypes.array,
  aspectRatio: PropTypes.string,
  showThumbnails: PropTypes.bool,
  emptyLabel: PropTypes.string,
  rounded: PropTypes.bool,
};
