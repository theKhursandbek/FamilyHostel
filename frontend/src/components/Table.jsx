import PropTypes from "prop-types";

/**
 * Coerce whatever the caller passes (array, paginated `{results: []}`,
 * `null`, single object) into a plain array of rows so `.map` never throws.
 */
function toRows(data) {
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object") {
    if (Array.isArray(data.results)) return data.results;
    if (Array.isArray(data.data)) return data.data;
  }
  return [];
}

function Table({ columns, data, onRowClick, emptyMessage = "No data found." }) {
  const rows = toRows(data);

  if (rows.length === 0) {
    return <div className="table-empty">{emptyMessage}</div>;
  }

  return (
    <div className="table-wrapper">
      <table className="table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr
              key={row.id ?? idx}
              onClick={() => onRowClick?.(row)}
              style={{ cursor: onRowClick ? "pointer" : "default" }}
            >
              {columns.map((col) => (
                <td key={col.key}>
                  {col.render ? col.render(row[col.key], row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

Table.propTypes = {
  columns: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      render: PropTypes.func,
    })
  ).isRequired,
  // Accept array, paginated `{results: []}`, null, or undefined
  data: PropTypes.oneOfType([PropTypes.array, PropTypes.object]),
  onRowClick: PropTypes.func,
  emptyMessage: PropTypes.string,
};

export default Table;
