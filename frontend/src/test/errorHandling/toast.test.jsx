import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ToastProvider, useToast } from "../../context/ToastContext";

// Helper component that triggers toasts for testing
function ToastTrigger() {
  const toast = useToast();
  return (
    <div>
      <button onClick={() => toast.success("Saved!")}>Success</button>
      <button onClick={() => toast.error("Failed!")}>Error</button>
      <button onClick={() => toast.warning("Watch out!")}>Warning</button>
    </div>
  );
}

describe("ToastContext – error handling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("shows success toast", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Success"));
    expect(screen.getByText("Saved!")).toBeInTheDocument();
  });

  it("shows error toast", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Error"));
    expect(screen.getByText("Failed!")).toBeInTheDocument();
  });

  it("shows warning toast", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Warning"));
    expect(screen.getByText("Watch out!")).toBeInTheDocument();
  });

  it("auto-dismisses success toast after 4s", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Success"));
    expect(screen.getByText("Saved!")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4500);
    });
    expect(screen.queryByText("Saved!")).not.toBeInTheDocument();
  });

  it("auto-dismisses error toast after 6s", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Error"));
    expect(screen.getByText("Failed!")).toBeInTheDocument();

    // Still visible at 5s
    act(() => {
      vi.advanceTimersByTime(5500);
    });
    expect(screen.getByText("Failed!")).toBeInTheDocument();

    // Gone after 6s
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.queryByText("Failed!")).not.toBeInTheDocument();
  });

  it("can show multiple toasts at once", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Success"));
    fireEvent.click(screen.getByText("Error"));
    expect(screen.getByText("Saved!")).toBeInTheDocument();
    expect(screen.getByText("Failed!")).toBeInTheDocument();
  });

  it("removes toast on dismiss click", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Success"));
    expect(screen.getByText("Saved!")).toBeInTheDocument();

    // Click the dismiss button (✕)
    const dismissBtn = screen.getByText("Saved!").closest(".toast")?.querySelector(".toast-close");
    if (dismissBtn) {
      fireEvent.click(dismissBtn);
      expect(screen.queryByText("Saved!")).not.toBeInTheDocument();
    }
  });

  it("throws when useToast is called outside ToastProvider", () => {
    function BadComponent() {
      useToast();
      return null;
    }
    expect(() => render(<BadComponent />)).toThrow(
      "useToast must be used within a ToastProvider"
    );
  });
});
