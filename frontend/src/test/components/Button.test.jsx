import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Button from "../../components/Button";

describe("Button", () => {
  it("renders children text", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  it("applies primary variant by default", () => {
    render(<Button>Primary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("btn-primary");
  });

  it("applies custom variant", () => {
    render(<Button variant="danger">Danger</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("btn-danger");
  });

  it("applies small size class", () => {
    render(<Button size="sm">Small</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("btn-sm");
  });

  it("is disabled when disabled prop is true", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("calls onClick handler", () => {
    const handler = vi.fn();
    render(<Button onClick={handler}>Click</Button>);
    fireEvent.click(screen.getByRole("button"));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not fire onClick when disabled", () => {
    const handler = vi.fn();
    render(<Button disabled onClick={handler}>Click</Button>);
    fireEvent.click(screen.getByRole("button"));
    expect(handler).not.toHaveBeenCalled();
  });

  it("defaults to type='button'", () => {
    render(<Button>Btn</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });

  it("accepts type='submit'", () => {
    render(<Button type="submit">Submit</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "submit");
  });
});
