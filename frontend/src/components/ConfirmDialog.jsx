import PropTypes from "prop-types";
import Modal from "./Modal";
import Button from "./Button";

/**
 * Reusable confirmation dialog — replaces the native `window.confirm()` with a
 * branded, accessible modal. Supports a destructive (`danger`) tone, a busy
 * state while the async action runs, and optional rich `children` body.
 *
 *   <ConfirmDialog
 *     isOpen={open}
 *     title="Cancel booking?"
 *     message="This frees the room. No refund is issued."
 *     tone="danger"
 *     confirmLabel="Cancel booking"
 *     loading={busy}
 *     onConfirm={handleCancel}
 *     onClose={() => setOpen(false)}
 *   />
 */
function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title = "Are you sure?",
  message,
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "primary",
  loading = false,
}) {
  const handleClose = () => {
    if (loading) return; // don't allow dismiss mid-flight
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={title} size="default">
      <div className="confirm-dialog">
        {message && <p className="confirm-dialog__message">{message}</p>}
        {children}
        <div className="confirm-dialog__actions">
          <Button variant="secondary" onClick={handleClose} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? "Please wait…" : confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

ConfirmDialog.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  title: PropTypes.string,
  message: PropTypes.string,
  children: PropTypes.node,
  confirmLabel: PropTypes.string,
  cancelLabel: PropTypes.string,
  tone: PropTypes.oneOf(["primary", "danger"]),
  loading: PropTypes.bool,
};

export default ConfirmDialog;
