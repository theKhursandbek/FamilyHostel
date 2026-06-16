import { useState, useEffect, useRef, useCallback } from "react";
import PropTypes from "prop-types";
import { X } from "lucide-react";
import Button from "./Button";
import { captureVideoFrame, previewUrl } from "../utils/imageCompression";

/**
 * Live in-app camera for cleaning verification.
 *
 * Anti-cheat by design: there is NO file input. Staff can only submit frames
 * captured live from the device camera, one per zone, in order. Each frame is
 * downscaled + JPEG-compressed before it leaves the device.
 *
 * Flow per zone: viewfinder → Capture → freeze/preview → Retake | Use Photo →
 * next zone. After all required zones (+ optional extra) → Submit All.
 */

const ZONES = [
  { key: "bed", label: "Bed & sleeping area", hint: "Show the made bed and fresh linen." },
  { key: "bathroom", label: "Bathroom", hint: "Toilet, sink, towels and floor." },
  { key: "floor", label: "Floor & general view", hint: "Whole room — floor must be clear." },
  { key: "trash", label: "Trash bin & surfaces", hint: "Emptied bin and wiped surfaces." },
];

function CameraCapture({ isOpen, onClose, onSubmit, submitting = false }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [stepIndex, setStepIndex] = useState(0);
  // shots: { [zoneKey]: { file, url } }
  const [shots, setShots] = useState({});
  const [frozen, setFrozen] = useState(null); // { file, url } awaiting confirm

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const startStream = useCallback(async () => {
    setError("");
    setReady(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setReady(true);
    } catch {
      setError(
        "Camera access is required to verify cleaning. Open this page on your " +
        "phone and allow camera access in your browser settings.",
      );
    }
  }, []);

  // Open/close lifecycle.
  useEffect(() => {
    if (isOpen) {
      setStepIndex(0);
      setShots({});
      setFrozen(null);
      startStream();
    } else {
      stopStream();
    }
    return () => stopStream();
  }, [isOpen, startStream, stopStream]);

  // Revoke object URLs on unmount to avoid leaks.
  useEffect(() => {
    return () => {
      Object.values(shots).forEach((s) => s?.url && URL.revokeObjectURL(s.url));
      if (frozen?.url) URL.revokeObjectURL(frozen.url);
    };
  }, [shots, frozen]);

  if (!isOpen) return null;

  const currentZone = ZONES[stepIndex];
  const isExtraStep = stepIndex >= ZONES.length;
  const capturedCount = Object.keys(shots).length;
  const allRequiredDone = ZONES.every((z) => shots[z.key]);

  const handleCapture = async () => {
    if (!videoRef.current || !ready) return;
    const zoneKey = isExtraStep ? "extra" : currentZone.key;
    try {
      const file = await captureVideoFrame(videoRef.current, zoneKey);
      setFrozen({ file, url: previewUrl(file) });
    } catch {
      setError("Could not capture the photo. Please try again.");
    }
  };

  const handleRetake = () => {
    if (frozen?.url) URL.revokeObjectURL(frozen.url);
    setFrozen(null);
  };

  const handleUsePhoto = () => {
    const zoneKey = isExtraStep ? "extra" : currentZone.key;
    setShots((prev) => {
      const next = { ...prev };
      if (next[zoneKey]?.url) URL.revokeObjectURL(next[zoneKey].url);
      next[zoneKey] = frozen;
      return next;
    });
    setFrozen(null);
    if (stepIndex < ZONES.length) setStepIndex((i) => i + 1);
  };

  const handleSubmit = () => {
    const items = ZONES.filter((z) => shots[z.key]).map((z) => ({
      zone: z.key,
      file: shots[z.key].file,
    }));
    if (shots.extra) items.push({ zone: "extra", file: shots.extra.file });
    onSubmit(items);
  };

  const progressLabel = isExtraStep
    ? "Optional extra photo"
    : `Photo ${stepIndex + 1}/${ZONES.length} — ${currentZone.label}`;

  return (
    <div className="cam-overlay" role="dialog" aria-modal="true" aria-label="Camera capture">
      <div className="cam-shell">
        <header className="cam-head">
          <span className="cam-head__title">{progressLabel}</span>
          <button type="button" className="cam-head__close" onClick={onClose} aria-label="Close camera">
            <X size={20} strokeWidth={2} aria-hidden />
          </button>
        </header>

        {/* Progress dots */}
        <div className="cam-dots">
          {ZONES.map((z, i) => (
            <span
              key={z.key}
              className={`cam-dot${shots[z.key] ? " is-done" : ""}${i === stepIndex && !isExtraStep ? " is-active" : ""}`}
              title={z.label}
            />
          ))}
        </div>

        <div className="cam-stage">
          {error ? (
            <div className="cam-error">
              <p>{error}</p>
              <Button size="sm" variant="secondary" onClick={startStream}>Try again</Button>
            </div>
          ) : (
            <>
              {/* Live viewfinder (hidden while a frame is frozen for review) */}
              <video
                ref={videoRef}
                className="cam-video"
                playsInline
                muted
                style={{ display: frozen ? "none" : "block" }}
              />
              {frozen && (
                <img src={frozen.url} alt="Captured preview" className="cam-preview" />
              )}
              {!ready && !frozen && <div className="cam-loading">Starting camera…</div>}
              {!frozen && currentZone && !isExtraStep && (
                <div className="cam-hint">{currentZone.hint}</div>
              )}
            </>
          )}
        </div>

        <footer className="cam-actions">
          {!error && !frozen && (
            <>
              <Button
                variant="primary"
                onClick={handleCapture}
                disabled={!ready || submitting}
                className="cam-shutter"
              >
                {isExtraStep ? "Capture extra" : "Capture"}
              </Button>
              {allRequiredDone && (
                <Button variant="secondary" onClick={handleSubmit} disabled={submitting}>
                  {submitting ? "Submitting…" : `Submit ${capturedCount} photo(s)`}
                </Button>
              )}
            </>
          )}

          {!error && frozen && (
            <>
              <Button variant="secondary" onClick={handleRetake} disabled={submitting}>
                Retake
              </Button>
              <Button variant="primary" onClick={handleUsePhoto} disabled={submitting}>
                Use photo
              </Button>
            </>
          )}
        </footer>
      </div>
    </div>
  );
}

CameraCapture.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
  submitting: PropTypes.bool,
};

export default CameraCapture;
