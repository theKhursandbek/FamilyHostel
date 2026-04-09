import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loader from "../../components/Loader";

describe("Loader", () => {
  it("renders default loading message", () => {
    render(<Loader />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders custom loading message", () => {
    render(<Loader message="Fetching data..." />);
    expect(screen.getByText("Fetching data...")).toBeInTheDocument();
  });

  it("renders spinner element", () => {
    const { container } = render(<Loader />);
    expect(container.querySelector(".loader-spinner")).toBeInTheDocument();
  });
});
