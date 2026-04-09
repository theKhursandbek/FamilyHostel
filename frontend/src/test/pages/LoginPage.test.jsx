import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

// Mock auth context
const mockLogin = vi.fn();
vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: false,
    login: mockLogin,
  }),
}));

import LoginPage from "../../pages/LoginPage";

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

describe("LoginPage – error handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows validation error when fields are empty", async () => {
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(screen.getByText("Phone and password are required.")).toBeInTheDocument();
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it("shows API error message from server", async () => {
    const user = userEvent.setup();
    const apiError = {
      response: {
        data: { non_field_errors: ["Invalid phone or password."] },
      },
    };
    mockLogin.mockRejectedValue(apiError);

    renderLogin();
    await user.type(screen.getByPlaceholderText("+998901234567"), "+998111111111");
    await user.type(screen.getByPlaceholderText("Enter password"), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Invalid phone or password.")).toBeInTheDocument();
    });
  });

  it("shows detail error from server when non_field_errors is absent", async () => {
    const user = userEvent.setup();
    const apiError = {
      response: {
        data: { detail: "Account locked." },
      },
    };
    mockLogin.mockRejectedValue(apiError);

    renderLogin();
    await user.type(screen.getByPlaceholderText("+998901234567"), "+998111111111");
    await user.type(screen.getByPlaceholderText("Enter password"), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Account locked.")).toBeInTheDocument();
    });
  });

  it("shows network error when there is no response (network down)", async () => {
    const user = userEvent.setup();
    const networkError = new Error("Network Error");
    // No .response property = network error
    mockLogin.mockRejectedValue(networkError);

    renderLogin();
    await user.type(screen.getByPlaceholderText("+998901234567"), "+998111111111");
    await user.type(screen.getByPlaceholderText("Enter password"), "pass123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Network error. Please check your connection.")).toBeInTheDocument();
    });
  });

  it("shows fallback 'Invalid credentials' when response has no detail", async () => {
    const user = userEvent.setup();
    const apiError = {
      response: { data: {} },
    };
    mockLogin.mockRejectedValue(apiError);

    renderLogin();
    await user.type(screen.getByPlaceholderText("+998901234567"), "+998111111111");
    await user.type(screen.getByPlaceholderText("Enter password"), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials. Please try again.")).toBeInTheDocument();
    });
  });

  it("disables inputs and button during loading", async () => {
    const user = userEvent.setup();
    // Make login hang so we can check loading state
    mockLogin.mockReturnValue(new Promise(() => {}));

    renderLogin();
    await user.type(screen.getByPlaceholderText("+998901234567"), "+998111111111");
    await user.type(screen.getByPlaceholderText("Enter password"), "pass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("+998901234567")).toBeDisabled();
      expect(screen.getByPlaceholderText("Enter password")).toBeDisabled();
      expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();
    });
  });

  it("clears previous error before new submit", async () => {
    const user = userEvent.setup();
    // First call fails
    mockLogin.mockRejectedValueOnce({ response: { data: { detail: "Error 1" } } });
    // Second call hangs
    mockLogin.mockReturnValueOnce(new Promise(() => {}));

    renderLogin();
    await user.type(screen.getByPlaceholderText("+998901234567"), "+998111111111");
    await user.type(screen.getByPlaceholderText("Enter password"), "pass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Error 1")).toBeInTheDocument();
    });

    // Submit again — error should clear
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    expect(screen.queryByText("Error 1")).not.toBeInTheDocument();
  });
});
