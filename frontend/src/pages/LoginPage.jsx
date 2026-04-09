import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Already logged in → redirect to dashboard
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!phone.trim() || !password.trim()) {
      setError("Phone and password are required.");
      return;
    }

    setLoading(true);
    try {
      await login(phone.trim(), password);
    } catch (err) {
      const detail =
        err.response?.data?.non_field_errors?.[0] ||
        err.response?.data?.detail ||
        "Invalid credentials. Please try again.";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "80px auto", padding: 24 }}>
      <h1>Login</h1>
      <p className="text-secondary" style={{ marginBottom: 24 }}>
        Sign in to the admin panel
      </p>

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      <div className="card" style={{ padding: 32 }}>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="phone" className="label">
              Phone
            </label>
            <input
              id="phone"
              type="text"
              className="input"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+998901234567"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password" className="label">
              Password
            </label>
            <input
              id="password"
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ width: "100%" }}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginPage;
