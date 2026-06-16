/**
 * Client-side image compression for cleaning verification photos.
 *
 * A captured camera frame (or video element) is drawn to a canvas, downscaled
 * to a sane maximum edge, and exported as a JPEG blob. This cuts a ~3-5 MB raw
 * phone frame to ~250-350 KB before upload — faster on cheap phones and far
 * cheaper to store. The server re-compresses + strips EXIF as a backstop.
 */

const DEFAULT_MAX_EDGE = 1600;
const DEFAULT_QUALITY = 0.75;

/**
 * Draw a source (video frame or image) to an offscreen canvas, downscaled.
 * @param {HTMLVideoElement|HTMLImageElement|HTMLCanvasElement} source
 * @param {number} maxEdge
 * @returns {HTMLCanvasElement}
 */
function drawDownscaled(source, maxEdge) {
  const sw = source.videoWidth || source.naturalWidth || source.width;
  const sh = source.videoHeight || source.naturalHeight || source.height;
  const scale = Math.min(1, maxEdge / Math.max(sw, sh));
  const dw = Math.round(sw * scale);
  const dh = Math.round(sh * scale);

  const canvas = document.createElement("canvas");
  canvas.width = dw;
  canvas.height = dh;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(source, 0, 0, dw, dh);
  return canvas;
}

/**
 * Compress a source to a JPEG Blob.
 * @param {HTMLVideoElement|HTMLImageElement|HTMLCanvasElement} source
 * @param {{ maxEdge?: number, quality?: number }} [opts]
 * @returns {Promise<Blob>}
 */
export function compressToBlob(source, opts = {}) {
  const { maxEdge = DEFAULT_MAX_EDGE, quality = DEFAULT_QUALITY } = opts;
  const canvas = drawDownscaled(source, maxEdge);
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Compression failed"))),
      "image/jpeg",
      quality,
    );
  });
}

/**
 * Capture the current frame of a playing <video> as a compressed JPEG File.
 * @param {HTMLVideoElement} video
 * @param {string} zone - zone label, used in the filename
 * @param {{ maxEdge?: number, quality?: number }} [opts]
 * @returns {Promise<File>}
 */
export async function captureVideoFrame(video, zone, opts = {}) {
  const blob = await compressToBlob(video, opts);
  return new File([blob], `${zone}.jpg`, { type: "image/jpeg" });
}

/**
 * Make a short-lived object URL for previewing a blob/file.
 * @param {Blob|File} blob
 * @returns {string}
 */
export function previewUrl(blob) {
  return URL.createObjectURL(blob);
}
