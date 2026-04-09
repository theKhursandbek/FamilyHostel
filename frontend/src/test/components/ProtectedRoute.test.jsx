import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ProtectedRoute from "../../components/ProtectedRoute";

// Mock useAuth
vi.mock("../../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "../../context/AuthContext";

describe("ProtectedRoute", () => {
  it("renders children when authenticated", () => {
    useAuth.mockReturnValue({ isAuthenticated: true });
    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );
    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  it("redirects to /login when not authenticated", () => {
    useAuth.mockReturnValue({ isAuthenticated: false });
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });
});
