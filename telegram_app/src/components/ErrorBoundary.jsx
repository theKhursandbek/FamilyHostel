import { Component } from "react";

/**
 * Top-level error boundary. Catches any unhandled render/lifecycle error
 * and shows a friendly recovery screen instead of a blank white page.
 *
 * Must be a class component — React only supports error boundaries
 * via getDerivedStateFromError / componentDidCatch in class components.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
    this.handleReset = this.handleReset.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Log to console for devtools; extend to Sentry here if needed.
    console.error("[ErrorBoundary]", error, info?.componentStack);
  }

  handleReset() {
    this.setState({ hasError: false, error: null });
    // Navigate to root as a clean recovery point.
    try { window.location.href = "/"; } catch { /* ignore */ }
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="error-boundary">
        <div className="error-boundary__icon" aria-hidden="true">⚠️</div>
        <h2 className="error-boundary__title">Xatolik yuz berdi</h2>
        <p className="error-boundary__sub">Something went wrong. Please try again.</p>
        <button
          type="button"
          className="btn btn-primary error-boundary__btn"
          onClick={this.handleReset}
        >
          Reload
        </button>
      </div>
    );
  }
}
