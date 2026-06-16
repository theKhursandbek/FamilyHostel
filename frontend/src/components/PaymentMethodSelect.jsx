import PropTypes from "prop-types";
import { Banknote, CreditCard, QrCode, ArrowLeftRight } from "lucide-react";

/**
 * The four cash-movement methods (mirrors the backend `PaymentMethod` choices).
 * Exported so callers can reuse the canonical list/labels if needed.
 */
export const PAYMENT_METHODS = [
  { value: "cash", label: "Cash", Icon: Banknote },
  { value: "terminal", label: "Terminal", Icon: CreditCard },
  { value: "qr", label: "QR code", Icon: QrCode },
  { value: "card_transfer", label: "Card transfer", Icon: ArrowLeftRight },
];

/**
 * Button-based payment-method selector.
 *
 * Renders the four methods as a group of standalone, single-select buttons
 * (an accessible `radiogroup`) — never a dropdown. Exactly one button is
 * active at a time.
 *
 *   <PaymentMethodSelect value={method} onChange={setMethod} />
 */
function PaymentMethodSelect({
  value,
  onChange,
  disabled = false,
  label = "Payment method",
  id = "paymethod",
}) {
  return (
    <div className="form-group paymethod">
      {label && (
        <span className="label" id={`${id}-label`}>{label}</span>
      )}
      <div
        className="paymethod__grid"
        role="radiogroup"
        aria-labelledby={label ? `${id}-label` : undefined}
      >
        {PAYMENT_METHODS.map(({ value: v, label: lbl, Icon }) => {
          const active = value === v;
          return (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={active}
              className={`paymethod__btn ${active ? "is-active" : ""}`}
              onClick={() => onChange(v)}
              disabled={disabled}
            >
              <Icon size={18} className="paymethod__icon" aria-hidden="true" />
              <span className="paymethod__label">{lbl}</span>
              <span className="paymethod__check" aria-hidden="true" />
            </button>
          );
        })}
      </div>
    </div>
  );
}

PaymentMethodSelect.propTypes = {
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  label: PropTypes.string,
  id: PropTypes.string,
};

export default PaymentMethodSelect;
