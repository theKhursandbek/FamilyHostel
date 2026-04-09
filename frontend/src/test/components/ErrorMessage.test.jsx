import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ErrorMessage from "../../components/ErrorMessage";

describe("ErrorMessage", () => {
  it("renders default error message", () => {
    render(<ErrorMessage />);
    expect(screen.getByText("Something went wrong.")).toBeInTheDocument();
  });

  it("renders custom error message", () => {
    render(<ErrorMessage message="Server error" />);
    expect(screen.getByText("Server error")).toBeInTheDocument();
  });

  it("shows retry button when onRetry is provided", () => {
    render(<ErrorMessage message="Oops" onRetry={() => {}} />);
    expect(screen.getByText("Try again")).toBeInTheDocument();
  });

  it("does not show retry button without onRetry", () => {
    render(<ErrorMessage message="Oops" />);
    expect(screen.queryByText("Try again")).not.toBeInTheDocument();
  });

  it("calls onRetry when retry button is clicked", () => {
    const handler = vi.fn();
    render(<ErrorMessage message="Error" onRetry={handler} />);
    fireEvent.click(screen.getByText("Try again"));
    expect(handler).toHaveBeenCalledTimes(1);
  });
});
