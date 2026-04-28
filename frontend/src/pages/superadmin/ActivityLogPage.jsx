import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import PropTypes from "prop-types";
import {
  listAuditLogsPaged,
  getAuditLogFacets,
  listSuspiciousActivities,
  undoAuditLog,
  redoAuditLog,
} from "../../services/ceoService";
import Button from "../../components/Button";
import Select from "../../components/Select";
import Loader from "../../components/Loader";
import ErrorMessage from "../../components/ErrorMessage";
import Table from "../../components/Table";

// ---------------------------------------------------------------------------
// Live Activity — Audit log + Suspicious activity
//
// Audit tab: filterable (When range, Role, Action, Entity, ID, User) +
// server-side paginated (page_size 20). Rows expand to reveal before/after
// JSON. Auto-refresh refetches the current page silently.
// ---------------------------------------------------------------------------

const TABS = [
  { id: "audit", label: "Audit log" },
  { id: "suspicious", label: "Suspicious activity" },
];

const REFRESH_OPTIONS = [
  { value: "0", label: "Off" },
  { value: "10", label: "10 s" },
  { value: "30", label: "30 s" },
  { value: "60", label: "60 s" },
];

const PAGE_SIZE_OPTIONS = [
  { value: "10", label: "10 / page" },
  { value: "20", label: "20 / page" },
  { value: "50", label: "50 / page" },
  { value: "100", label: "100 / page" },
];

const EMPTY_FILTERS = {
  created_after: "",
  created_before: "",
  role: "",
  action: "",
  entity_type: "",
  user: "",
  search: "",
};

function toIsoOrEmpty(localValue) {
  if (!localValue) return "";
  const d = new Date(localValue);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString();
}

function formatRelative(dt) {
  if (!dt) return "—";
  const d = new Date(dt);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return `${Math.max(1, Math.floor(diff))}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
}

function activeCountLabel(count) {
  if (count <= 0) return "No filters applied";
  const noun = count === 1 ? "filter" : "filters";
  return `${count} ${noun} active`;
}

function titleCase(s) {
  if (!s) return s;
  return s
    .replaceAll(/[_-]+/g, " ")
    .replaceAll(/\b\w/g, (c) => c.toUpperCase());
}

/** Pretty-print backend action codes like "penalty.created" → "Penalty · Created". */
function formatAction(value) {
  if (!value) return value;
  const parts = value.split(".");
  return parts.map(titleCase).join(" · ");
}

function formatRole(value) {
  if (!value) return value;
  return titleCase(value);
}

/** Entity types come PascalCase (e.g. "Penalty") — keep them but split words. */
function formatEntity(value) {
  if (!value) return value;
  return value.replaceAll(/([a-z])([A-Z])/g, "$1 $2");
}

function ActivityLogPage() {
  const [tab, setTab] = useState("audit");

  // Audit state
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [pendingFilters, setPendingFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState("10");
  const [audit, setAudit] = useState({
    results: [],
    count: 0,
    total_pages: 1,
    page: 1,
  });
  const [facets, setFacets] = useState({
    roles: [],
    actions: [],
    entity_types: [],
  });
  const [expandedId, setExpandedId] = useState(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [restoreBusyId, setRestoreBusyId] = useState(null);

  // Suspicious state
  const [suspicious, setSuspicious] = useState([]);

  // Common state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshSec, setRefreshSec] = useState("30");
  const [lastUpdated, setLastUpdated] = useState(null);
  const timerRef = useRef(null);

  const auditQuery = useMemo(() => {
    const q = { ordering: "-created_at", page, page_size: pageSize };
    if (filters.created_after) q.created_after = toIsoOrEmpty(filters.created_after);
    if (filters.created_before) q.created_before = toIsoOrEmpty(filters.created_before);
    if (filters.role) q.role = filters.role;
    if (filters.action) q.action = filters.action;
    if (filters.entity_type) q.entity_type = filters.entity_type;
    if (filters.user) q.user = filters.user;
    if (filters.search) q.search = filters.search;
    return q;
  }, [filters, page, pageSize]);

  const fetchData = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      setError(null);
      try {
        if (tab === "audit") {
          const data = await listAuditLogsPaged(auditQuery);
          setAudit({
            results: data.results || [],
            count: data.count ?? 0,
            total_pages: data.total_pages ?? 1,
            page: data.page ?? 1,
          });
        } else {
          const data = await listSuspiciousActivities({ ordering: "-updated_at" });
          setSuspicious(Array.isArray(data) ? data : data?.results || []);
        }
        setLastUpdated(new Date());
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to load activity.");
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [tab, auditQuery],
  );

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (tab !== "audit") return;
    getAuditLogFacets()
      .then(setFacets)
      .catch(() => {
        /* facets are optional */
      });
  }, [tab]);

  useEffect(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    const sec = Number(refreshSec);
    if (sec > 0) {
      timerRef.current = setInterval(() => fetchData(true), sec * 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [refreshSec, fetchData]);

  // Whenever the active filters or page size change, jump back to page 1
  useEffect(() => {
    setPage(1);
  }, [filters, pageSize]);

  const applyFilters = () => setFilters(pendingFilters);
  const resetFilters = () => {
    setPendingFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
  };
  const updatePending = (patch) =>
    setPendingFilters((prev) => ({ ...prev, ...patch }));

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((v) => v !== "" && v !== null).length,
    [filters],
  );

  const handleRestore = useCallback(
    async (row, direction) => {
      if (!row?.id) return;
      const verb = direction === "undo" ? "Undo" : "Redo";
      const label = formatAction(row.action) || row.action;
      if (!globalThis.confirm(`${verb} "${label}" on ${row.entity_type} #${row.entity_id}?`)) {
        return;
      }
      setRestoreBusyId(row.id);
      setError(null);
      try {
        const fn = direction === "undo" ? undoAuditLog : redoAuditLog;
        const result = await fn(row.id);
        await fetchData(true);
        if (result?.summary) {
          // Soft notice — the new audit row will be visible in the list.
          // eslint-disable-next-line no-console
          console.info(`[restore] ${result.summary}`);
        }
      } catch (err) {
        const detail =
          err.response?.data?.detail ||
          err.response?.data?.message ||
          `Failed to ${direction} this action.`;
        setError(detail);
      } finally {
        setRestoreBusyId(null);
      }
    },
    [fetchData],
  );

  const suspiciousColumns = [
    {
      key: "updated_at",
      label: "Updated",
      render: (v) => (v ? new Date(v).toLocaleString() : "—"),
    },
    { key: "activity_type", label: "Type" },
    { key: "ip_address", label: "IP" },
    {
      key: "account_email",
      label: "User",
      render: (v, row) =>
        v || row.account_phone || (row.account ? `acc#${row.account}` : "—"),
    },
    { key: "count", label: "Count" },
    {
      key: "is_blocked",
      label: "Blocked",
      render: (v) => (
        <span className={`badge ${v ? "badge-danger" : "badge-success"}`}>
          {v ? "Blocked" : "OK"}
        </span>
      ),
    },
    {
      key: "blocked_until",
      label: "Until",
      render: (v) => (v ? new Date(v).toLocaleString() : "—"),
    },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Live Activity</h1>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="text-muted" style={{ fontSize: 13 }}>
            {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : ""}
          </span>
          <div style={{ width: 130 }}>
            <Select
              value={refreshSec}
              onChange={setRefreshSec}
              options={REFRESH_OPTIONS}
            />
          </div>
          <Button variant="ghost" onClick={() => fetchData()}>
            Refresh
          </Button>
        </div>
      </div>

      <div
        className="card"
        style={{
          display: "flex",
          gap: 8,
          padding: 6,
          marginBottom: 16,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        {TABS.map((t) => (
          <Button
            key={t.id}
            variant={tab === t.id ? "primary" : "ghost"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </Button>
        ))}
        {tab === "audit" && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            {activeFilterCount > 0 && (
              <Button variant="ghost" onClick={resetFilters}>
                Clear filters
              </Button>
            )}
            <Button
              variant={filtersOpen || activeFilterCount > 0 ? "primary" : "secondary"}
              onClick={() => setFiltersOpen((v) => !v)}
            >
              {filtersOpen ? "Hide filters" : "Filters"}
              {activeFilterCount > 0 && (
                <span
                  style={{
                    marginLeft: 8,
                    padding: "1px 8px",
                    borderRadius: 999,
                    background: "var(--bg-card)",
                    color: "var(--brand-primary)",
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  {activeFilterCount}
                </span>
              )}
            </Button>
          </div>
        )}
      </div>

      {tab === "audit" && filtersOpen && (
        <AuditFilterBar
          pending={pendingFilters}
          facets={facets}
          activeCount={activeFilterCount}
          onChange={updatePending}
          onApply={() => {
            applyFilters();
            setFiltersOpen(false);
          }}
          onReset={resetFilters}
        />
      )}

      {loading && <Loader />}
      {!loading && error && (
        <ErrorMessage message={error} onRetry={() => fetchData()} />
      )}

      {!loading && !error && tab === "audit" && (
        <AuditList
          rows={audit.results}
          page={audit.page}
          totalPages={audit.total_pages}
          count={audit.count}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
          expandedId={expandedId}
          onToggleExpand={(id) =>
            setExpandedId((curr) => (curr === id ? null : id))
          }
          onRestore={handleRestore}
          restoreBusyId={restoreBusyId}
        />
      )}

      {!loading && !error && tab === "suspicious" && (
        <>
          {suspicious.length === 0 ? (
            <div className="empty-state">No suspicious activity recorded.</div>
          ) : (
            <Table columns={suspiciousColumns} data={suspicious} />
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

function AuditFilterBar({
  pending,
  facets,
  activeCount,
  onChange,
  onApply,
  onReset,
}) {
  const roleOptions = [
    { value: "", label: "All roles" },
    ...facets.roles.map((r) => ({ value: r, label: formatRole(r) })),
  ];
  const actionOptions = [
    { value: "", label: "All actions" },
    ...facets.actions.map((a) => ({ value: a, label: formatAction(a) })),
  ];
  const entityOptions = [
    { value: "", label: "All entities" },
    ...facets.entity_types.map((e) => ({ value: e, label: formatEntity(e) })),
  ];

  return (
    <div
      className="card"
      style={{
        marginBottom: 16,
        padding: 16,
        display: "grid",
        gap: 12,
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        alignItems: "end",
      }}
    >
      <FilterField label="From">
        <input
          type="datetime-local"
          className="input"
          value={pending.created_after}
          onChange={(e) => onChange({ created_after: e.target.value })}
        />
      </FilterField>
      <FilterField label="To">
        <input
          type="datetime-local"
          className="input"
          value={pending.created_before}
          onChange={(e) => onChange({ created_before: e.target.value })}
        />
      </FilterField>
      <FilterField label="Search action">
        <input
          type="text"
          className="input"
          placeholder="e.g. cash_session, paid, refund"
          value={pending.search}
          onChange={(e) => onChange({ search: e.target.value })}
        />
      </FilterField>
      <FilterField label="Role">
        <Select
          value={pending.role}
          onChange={(v) => onChange({ role: v })}
          options={roleOptions}
        />
      </FilterField>
      <FilterField label="Action">
        <Select
          value={pending.action}
          onChange={(v) => onChange({ action: v })}
          options={actionOptions}
        />
      </FilterField>
      <FilterField label="Entity">
        <Select
          value={pending.entity_type}
          onChange={(v) => onChange({ entity_type: v })}
          options={entityOptions}
        />
      </FilterField>
      <FilterField label="User">
        <input
          type="text"
          className="input"
          placeholder="Name, phone or telegram id"
          value={pending.user}
          onChange={(e) => onChange({ user: e.target.value })}
        />
      </FilterField>
      <div
        style={{
          display: "flex",
          gap: 8,
          gridColumn: "1 / -1",
          justifyContent: "flex-end",
          alignItems: "center",
        }}
      >
        <span
          className="text-muted"
          style={{ fontSize: 13, marginRight: "auto" }}
        >
          {activeCountLabel(activeCount)}
        </span>
        <Button variant="ghost" onClick={onReset}>
          Reset
        </Button>
        <Button variant="primary" onClick={onApply}>
          Apply
        </Button>
      </div>
    </div>
  );
}

AuditFilterBar.propTypes = {
  pending: PropTypes.object.isRequired,
  facets: PropTypes.object.isRequired,
  activeCount: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
  onApply: PropTypes.func.isRequired,
  onReset: PropTypes.func.isRequired,
};

function FilterField({ label, children }) {
  return (
    <div className="form-group" style={{ marginBottom: 0 }}>
      <label
        className="label"
        style={{
          fontSize: 12,
          textTransform: "uppercase",
          letterSpacing: 0.4,
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

FilterField.propTypes = {
  label: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
};

// ---------------------------------------------------------------------------
// Paginated list
// ---------------------------------------------------------------------------

function AuditList({
  rows,
  page,
  totalPages,
  count,
  pageSize,
  onPageChange,
  onPageSizeChange,
  expandedId,
  onToggleExpand,
  onRestore,
  restoreBusyId,
}) {
  if (rows.length === 0) {
    return <div className="empty-state">No matching audit log entries.</div>;
  }
  return (
    <div className="card" style={{ padding: 0, overflow: "visible" }}>
      <div
        className="table-wrapper"
        style={{
          marginTop: 0,
          boxShadow: "none",
          border: "none",
          borderTopLeftRadius: "var(--radius)",
          borderTopRightRadius: "var(--radius)",
        }}
      >
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: 32 }} aria-label="expand" />
              <th>When</th>
              <th>Role</th>
              <th>Action</th>
              <th>Entity</th>
              <th>ID</th>
              <th>User</th>
              <th style={{ width: 140, textAlign: "right" }}>Restore</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <RowGroup
                key={row.id}
                row={row}
                isOpen={expandedId === row.id}
                onToggle={() => onToggleExpand(row.id)}
                onRestore={onRestore}
                busy={restoreBusyId === row.id}
              />
            ))}
          </tbody>
        </table>
      </div>
      <PaginationBar
        page={page}
        totalPages={totalPages}
        count={count}
        pageSize={pageSize}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
      />
    </div>
  );
}

AuditList.propTypes = {
  rows: PropTypes.array.isRequired,
  page: PropTypes.number.isRequired,
  totalPages: PropTypes.number.isRequired,
  count: PropTypes.number.isRequired,
  pageSize: PropTypes.string.isRequired,
  onPageChange: PropTypes.func.isRequired,
  onPageSizeChange: PropTypes.func.isRequired,
  expandedId: PropTypes.number,
  onToggleExpand: PropTypes.func.isRequired,
  onRestore: PropTypes.func.isRequired,
  restoreBusyId: PropTypes.number,
};

function RowGroup({ row, isOpen, onToggle, onRestore, busy }) {
  const userLabel =
    row.account_name ||
    row.account_phone ||
    (row.account_telegram_id ? `tg:${row.account_telegram_id}` : null) ||
    (row.account ? `acc#${row.account}` : "—");

  const reversible = row.is_reversible === true;
  const state = row.restore_state || "not_reversible";
  const showUndo = reversible && state === "active";
  const showRedo = reversible && state === "undone";

  const stop = (e) => e.stopPropagation();
  const handleRestoreClick = (direction) => (e) => {
    e.stopPropagation();
    onRestore?.(row, direction);
  };

  return (
    <>
      <tr
        onClick={onToggle}
        style={{ cursor: "pointer" }}
        title={isOpen ? "Hide details" : "Show before / after data"}
      >
        <td style={{ textAlign: "center", color: "var(--text-secondary)" }}>
          {isOpen ? "▾" : "▸"}
        </td>
        <td>
          <div>{new Date(row.created_at).toLocaleString()}</div>
          <div className="text-muted" style={{ fontSize: 12 }}>
            {formatRelative(row.created_at)}
          </div>
        </td>
        <td>
          <span className="badge badge-accent">{formatRole(row.role) || "—"}</span>
        </td>
        <td style={{ fontWeight: 500 }}>{formatAction(row.action)}</td>
        <td>{formatEntity(row.entity_type)}</td>
        <td>{row.entity_id ?? "—"}</td>
        <td>{userLabel}</td>
        <td style={{ textAlign: "right" }} onClick={stop}>
          {showUndo && (
            <Button
              size="sm"
              variant="ghost"
              onClick={handleRestoreClick("undo")}
              disabled={busy}
              title="Reverse this action"
            >
              {busy ? "…" : "Undo"}
            </Button>
          )}
          {showRedo && (
            <Button
              size="sm"
              variant="ghost"
              onClick={handleRestoreClick("redo")}
              disabled={busy}
              title="Re-apply this action"
            >
              {busy ? "…" : "Redo"}
            </Button>
          )}
          {!reversible && (
            <span
              className="text-muted"
              style={{ fontSize: 12 }}
              title="This action cannot be reversed automatically"
            >
              —
            </span>
          )}
        </td>
      </tr>
      {isOpen && (
        <tr>
          <td />
          <td colSpan={7} style={{ background: "var(--bg-soft)" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 12,
                padding: 12,
              }}
            >
              <JsonBlock title="Before" value={row.before_data} />
              <JsonBlock title="After" value={row.after_data} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

RowGroup.propTypes = {
  row: PropTypes.object.isRequired,
  isOpen: PropTypes.bool.isRequired,
  onToggle: PropTypes.func.isRequired,
  onRestore: PropTypes.func,
  busy: PropTypes.bool,
};

function JsonBlock({ title, value }) {
  // Strip the private ``_raw`` payload (used by the restore service) from
  // the human-facing JSON view so operators only see the serializer shape.
  const visible = useMemo(() => {
    if (!value || typeof value !== "object" || Array.isArray(value)) return value;
    if (!("_raw" in value)) return value;
    const rest = { ...value };
    delete rest._raw;
    return rest;
  }, [value]);
  return (
    <div>
      <div
        style={{
          fontSize: 12,
          textTransform: "uppercase",
          letterSpacing: 0.4,
          color: "var(--text-secondary)",
          marginBottom: 4,
        }}
      >
        {title}
      </div>
      <pre
        style={{
          margin: 0,
          padding: 10,
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-sm)",
          fontSize: 12,
          maxHeight: 240,
          overflow: "auto",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {visible ? JSON.stringify(visible, null, 2) : "—"}
      </pre>
    </div>
  );
}

JsonBlock.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.any,
};

function PaginationBar({
  page,
  totalPages,
  count,
  pageSize,
  onPageChange,
  onPageSizeChange,
}) {
  const safeTotal = Math.max(1, totalPages || 1);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: 12,
        borderTop: "1px solid var(--border)",
        background: "var(--bg-card)",
        flexWrap: "wrap",
      }}
    >
      <span className="text-muted" style={{ fontSize: 13 }}>
        {count} record{count === 1 ? "" : "s"} • page {page} of {safeTotal}
      </span>
      <div
        style={{
          marginLeft: "auto",
          display: "flex",
          gap: 8,
          alignItems: "center",
        }}
      >
        <div style={{ width: 130 }}>
          <Select
            value={pageSize}
            onChange={onPageSizeChange}
            options={PAGE_SIZE_OPTIONS}
          />
        </div>
        <Button
          variant="ghost"
          onClick={() => onPageChange(1)}
          disabled={page <= 1}
        >
          « First
        </Button>
        <Button
          variant="ghost"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
        >
          ‹ Prev
        </Button>
        <Button
          variant="ghost"
          onClick={() => onPageChange(Math.min(safeTotal, page + 1))}
          disabled={page >= safeTotal}
        >
          Next ›
        </Button>
        <Button
          variant="ghost"
          onClick={() => onPageChange(safeTotal)}
          disabled={page >= safeTotal}
        >
          Last »
        </Button>
      </div>
    </div>
  );
}

PaginationBar.propTypes = {
  page: PropTypes.number.isRequired,
  totalPages: PropTypes.number.isRequired,
  count: PropTypes.number.isRequired,
  pageSize: PropTypes.string.isRequired,
  onPageChange: PropTypes.func.isRequired,
  onPageSizeChange: PropTypes.func.isRequired,
};

export default ActivityLogPage;
