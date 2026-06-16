import PropTypes from "prop-types";
import Modal from "./Modal";
import Button from "./Button";

/**
 * Cancel modal — routes between the two cancellation scenarios:
 *
 *   Scenario A (`can_cancel_extension`): the booking was extended, so the user
 *     can roll back *only the extra nights* (base stay survives) OR cancel the
 *     whole booking.
 *   Scenario B: a plain booking — cancel the whole thing.
 *
 * No money is ever refunded in either path.
 */
function CancelBookingModal({
  target,
  busyId,
  onClose,
  onCancelExtension,
  onCancelWhole,
}) {
  const busy = Boolean(busyId);
  const waiting = target && busyId === target.id;
  return (
    <Modal
      isOpen={Boolean(target)}
      onClose={() => { if (!busy) onClose(); }}
      title={target?.can_cancel_extension ? "Cancel what?" : "Cancel booking"}
    >
      {target && (
        <div className="confirm-dialog">
          {target.can_cancel_extension ? (
            <>
              <p className="confirm-dialog__message">
                This booking was extended. You can roll back just the extra
                nights (the original stay stays <strong>active</strong>) or
                cancel the whole booking. No money is refunded either way.
              </p>
              <div className="confirm-dialog__actions confirm-dialog__actions--stack">
                <Button variant="secondary" onClick={onCancelExtension} disabled={busy}>
                  {waiting ? "Please wait…" : "Roll back the extension only"}
                </Button>
                <Button variant="danger" onClick={onCancelWhole} disabled={busy}>
                  {waiting ? "Please wait…" : "Cancel the entire booking"}
                </Button>
                <Button variant="ghost" onClick={onClose} disabled={busy}>
                  Keep booking
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="confirm-dialog__message">
                Cancel the booking for room <strong>{target.room_number}</strong>?
                The room will be freed for new guests. No money is refunded.
              </p>
              <div className="confirm-dialog__actions">
                <Button variant="secondary" onClick={onClose} disabled={busy}>
                  Keep booking
                </Button>
                <Button variant="danger" onClick={onCancelWhole} disabled={busy}>
                  {waiting ? "Please wait…" : "Cancel booking"}
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </Modal>
  );
}

CancelBookingModal.propTypes = {
  target: PropTypes.object,
  busyId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  onClose: PropTypes.func.isRequired,
  onCancelExtension: PropTypes.func.isRequired,
  onCancelWhole: PropTypes.func.isRequired,
};

export default CancelBookingModal;
