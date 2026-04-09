import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Input from "../../components/Input";

describe("Input", () => {
  it("renders with label", () => {
    render(<Input label="Email" id="email" value="" onChange={() => {}} />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("renders without label", () => {
    render(<Input id="field" value="hello" onChange={() => {}} />);
    expect(screen.getByDisplayValue("hello")).toBeInTheDocument();
  });

  it("shows required asterisk when required", () => {
    render(<Input label="Name" id="name" required value="" onChange={() => {}} />);
    expect(screen.getByText("*")).toBeInTheDocument();
  });

  it("renders error message", () => {
    render(<Input label="Name" id="name" error="Required field" value="" onChange={() => {}} />);
    expect(screen.getByText("Required field")).toBeInTheDocument();
  });

  it("adds error class when error prop is set", () => {
    render(<Input id="name" error="Bad" value="" onChange={() => {}} />);
    const input = screen.getByDisplayValue("");
    expect(input.className).toContain("error");
  });

  it("calls onChange when typing", () => {
    const handler = vi.fn();
    render(<Input id="name" value="" onChange={handler} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "abc" } });
    expect(handler).toHaveBeenCalled();
  });

  it("is disabled when disabled prop is true", () => {
    render(<Input id="name" disabled value="" onChange={() => {}} />);
    expect(screen.getByRole("textbox")).toBeDisabled();
  });

  it("passes placeholder", () => {
    render(<Input id="name" placeholder="Enter name" value="" onChange={() => {}} />);
    expect(screen.getByPlaceholderText("Enter name")).toBeInTheDocument();
  });
});
