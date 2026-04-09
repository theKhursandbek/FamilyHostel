import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Modal from "../../components/Modal";

describe("Modal", () => {
  it("renders nothing when isOpen is false", () => {
    const { container } = render(
      <Modal isOpen={false} onClose={() => {}} title="Test">
        <p>Content</p>
      </Modal>
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders content when isOpen is true", () => {
    render(
      <Modal isOpen={true} onClose={() => {}} title="My Modal">
        <p>Modal body</p>
      </Modal>
    );
    expect(screen.getByText("My Modal")).toBeInTheDocument();
    expect(screen.getByText("Modal body")).toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={onClose} title="Test">
        <p>Body</p>
      </Modal>
    );
    fireEvent.click(screen.getByText("✕"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when Escape key is pressed", () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={onClose} title="Test">
        <p>Body</p>
      </Modal>
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when backdrop is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={onClose} title="Test">
        <p>Body</p>
      </Modal>
    );
    // Backdrop is the element with class "modal-backdrop"
    const backdrop = document.querySelector(".modal-backdrop");
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("displays the title in the header", () => {
    render(
      <Modal isOpen={true} onClose={() => {}} title="Booking Details">
        <p>Info</p>
      </Modal>
    );
    expect(screen.getByText("Booking Details")).toBeInTheDocument();
  });
});
