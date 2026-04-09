function ErrorMessage({ message = "Something went wrong.", onRetry }) {
  return (
    <div className="alert alert-error">
      <p style={{ margin: 0, fontWeight: 500 }}>{message}</p>
      {onRetry && (
        <button className="btn btn-danger btn-sm" onClick={onRetry} style={{ marginTop: 8 }}>
          Try again
        </button>
      )}
    </div>
  );
}

export default ErrorMessage;
