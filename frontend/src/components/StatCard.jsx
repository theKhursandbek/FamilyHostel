function StatCard({ title, value, subtitle }) {
  return (
    <div className="stat-card">
      <p className="stat-card-title">{title}</p>
      <p className="stat-card-value">{value}</p>
      {subtitle && <p className="stat-card-subtitle">{subtitle}</p>}
    </div>
  );
}

export default StatCard;
