function ErrorMessage({ message = "Something went wrong.", onRetry }) {
  return (
    <div
      style={{
        padding: 16,
        background: "#fef2f2",
        border: "1px solid #fecaca",
        borderRadius: 8,
        color: "#dc2626",
      }}
    >
      <p style={{ margin: 0, fontWeight: 500 }}>{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginTop: 8,
            padding: "6px 14px",
            background: "#dc2626",
            color: "#fff",
            border: "none",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          Try again
        </button>
      )}
    </div>
  );
}

export default ErrorMessage;
