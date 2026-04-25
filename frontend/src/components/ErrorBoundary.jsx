import { Component } from "react";
import PropTypes from "prop-types";

/**
 * App-wide error boundary.
 *
 * A render-time exception in any child component would otherwise unmount
 * the whole React tree and leave the user staring at a blank page.
 * This boundary catches it and shows a recoverable error UI instead.
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Surface to the dev console for debugging
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, info);
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  handleReload = () => {
    globalThis.location.reload();
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div style={{ padding: 32, color: "#f8fafc", maxWidth: 720, margin: "40px auto" }}>
        <h1 style={{ marginTop: 0 }}>⚠️ Something went wrong</h1>
        <p style={{ color: "#cbd5e1" }}>
          The page hit an unexpected error. The details are in your browser console.
        </p>
        <pre
          style={{
            background: "#0f172a",
            border: "1px solid #334155",
            borderRadius: 8,
            padding: 12,
            overflowX: "auto",
            fontSize: 13,
            color: "#fca5a5",
          }}
        >
          {String(error?.message || error)}
        </pre>
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button
            type="button"
            onClick={this.handleReset}
            style={{ padding: "8px 16px", borderRadius: 6, border: "1px solid #475569", background: "#1e293b", color: "#f8fafc", cursor: "pointer" }}
          >
            Try Again
          </button>
          <button
            type="button"
            onClick={this.handleReload}
            style={{ padding: "8px 16px", borderRadius: 6, border: 0, background: "#2563eb", color: "white", cursor: "pointer" }}
          >
            Reload Page
          </button>
        </div>
      </div>
    );
  }
}

ErrorBoundary.propTypes = {
  children: PropTypes.node.isRequired,
};

export default ErrorBoundary;
