function StatCard({ title, value, subtitle }) {
  return (
    <div
      style={{
        padding: 20,
        background: "#fff",
        border: "1px solid #e0e0e0",
        borderRadius: 8,
        minWidth: 200,
      }}
    >
      <p style={{ margin: 0, fontSize: 13, color: "#666" }}>{title}</p>
      <p style={{ margin: "8px 0 0", fontSize: 28, fontWeight: 600, color: "#333" }}>
        {value}
      </p>
      {subtitle && (
        <p style={{ margin: "4px 0 0", fontSize: 12, color: "#999" }}>
          {subtitle}
        </p>
      )}
    </div>
  );
}

export default StatCard;
