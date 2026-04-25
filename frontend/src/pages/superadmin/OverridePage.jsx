import { useState } from "react";
import { performOverride } from "../../services/ceoService";
import { useToast } from "../../context/ToastContext";
import Button from "../../components/Button";
import Input from "../../components/Input";
import Select from "../../components/Select";

const ENTITY_OPTIONS = [
  { value: "booking", label: "Booking" },
  { value: "room", label: "Room" },
  { value: "cleaning_task", label: "Cleaning Task" },
];

const ACTIONS_BY_ENTITY = {
  booking: [
    { value: "set_status", label: "Set status" },
    { value: "set_price", label: "Set final price" },
  ],
  room: [{ value: "set_status", label: "Set status" }],
  cleaning_task: [{ value: "set_status", label: "Set status" }],
};

const VALUE_CHOICES = {
  "booking|set_status": ["pending", "paid", "completed", "canceled"],
  "room|set_status": ["available", "booked", "occupied", "cleaning", "ready"],
  "cleaning_task|set_status": ["pending", "in_progress", "completed"],
};

function OverridePage() {
  const toast = useToast();
  const [entity, setEntity] = useState("booking");
  const [action, setAction] = useState("set_status");
  const [entityId, setEntityId] = useState("");
  const [value, setValue] = useState("paid");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState([]);

  const choicesKey = `${entity}|${action}`;
  const valueChoices = VALUE_CHOICES[choicesKey];

  const onEntityChange = (v) => {
    setEntity(v);
    const firstAction = ACTIONS_BY_ENTITY[v][0].value;
    setAction(firstAction);
    const c = VALUE_CHOICES[`${v}|${firstAction}`];
    setValue(c ? c[0] : "");
  };

  const onActionChange = (v) => {
    setAction(v);
    const c = VALUE_CHOICES[`${entity}|${v}`];
    setValue(c ? c[0] : "");
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!entityId) { toast.warning("Entity ID is required."); return; }
    if (!reason.trim()) { toast.warning("A reason is required."); return; }

    setBusy(true);
    try {
      const result = await performOverride({
        entity_type: entity,
        action,
        entity_id: Number(entityId),
        value: String(value),
        reason: reason.trim(),
      });
      toast.success(`Override applied: ${result.field} ${result.before} → ${result.after}`);
      setHistory((h) => [{ ...result, at: new Date().toISOString() }, ...h].slice(0, 20));
      setReason("");
    } catch (err) {
      const data = err.response?.data;
      const msg = data?.detail
        || (typeof data === "object" ? Object.values(data).flat().join(" ") : null)
        || "Override failed.";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>CEO Override</h1>
      </div>

      <div className="card">
        <p className="text-muted" style={{ marginTop: 0 }}>
          Apply an emergency override on any operation. Every action is recorded
          in the <strong>audit log</strong> with a mandatory reason.
        </p>

        <form onSubmit={submit}>
          <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))" }}>
            <div className="form-group">
              <label className="label" htmlFor="o-entity">Entity</label>
              <Select id="o-entity" value={entity} onChange={onEntityChange} options={ENTITY_OPTIONS} />
            </div>
            <div className="form-group">
              <label className="label" htmlFor="o-action">Action</label>
              <Select id="o-action" value={action} onChange={onActionChange} options={ACTIONS_BY_ENTITY[entity]} />
            </div>
            <Input
              id="o-id"
              label="Entity ID"
              type="number"
              min="1"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              required
            />
            <div className="form-group">
              <label className="label" htmlFor="o-value">New value</label>
              {valueChoices ? (
                <Select
                  id="o-value"
                  value={value}
                  onChange={setValue}
                  options={valueChoices.map((v) => ({ value: v, label: v }))}
                />
              ) : (
                <input
                  id="o-value"
                  className="input"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="Enter new value"
                />
              )}
            </div>
          </div>

          <div className="form-group" style={{ marginTop: 12 }}>
            <label className="label" htmlFor="o-reason">Reason (required)</label>
            <textarea
              id="o-reason"
              className="input"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain why this override is necessary"
            />
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
            <Button type="submit" variant="danger" disabled={busy}>
              {busy ? "Applying…" : "Apply override"}
            </Button>
          </div>
        </form>
      </div>

      {history.length > 0 && (
        <div className="card" style={{ marginTop: 24 }}>
          <h3 style={{ marginTop: 0 }}>Recent overrides (this session)</h3>
          <ul style={{ paddingLeft: 18, margin: 0 }}>
            {history.map((h, i) => (
              <li key={`${h.entity_type}-${h.entity_id}-${h.at}-${i}`} style={{ marginBottom: 4 }}>
                <code style={{ fontSize: 12 }}>
                  [{new Date(h.at).toLocaleTimeString()}] {h.entity_type}#{h.entity_id} {h.field}: {h.before} → {h.after}
                </code>
                <span className="text-muted"> — {h.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default OverridePage;
