import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Table from "../../components/Table";

const columns = [
  { key: "name", label: "Name" },
  { key: "status", label: "Status" },
];

const data = [
  { id: 1, name: "Alice", status: "active" },
  { id: 2, name: "Bob", status: "inactive" },
];

describe("Table", () => {
  it("renders column headers", () => {
    render(<Table columns={columns} data={data} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders data rows", () => {
    render(<Table columns={columns} data={data} />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("shows empty message when data is empty", () => {
    render(<Table columns={columns} data={[]} emptyMessage="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("shows default empty message", () => {
    render(<Table columns={columns} data={[]} />);
    expect(screen.getByText("No data found.")).toBeInTheDocument();
  });

  it("shows empty message when data is null", () => {
    render(<Table columns={columns} data={null} />);
    expect(screen.getByText("No data found.")).toBeInTheDocument();
  });

  it("calls onRowClick with row data", () => {
    const handler = vi.fn();
    render(<Table columns={columns} data={data} onRowClick={handler} />);
    fireEvent.click(screen.getByText("Alice"));
    expect(handler).toHaveBeenCalledWith(data[0]);
  });

  it("uses custom render function for columns", () => {
    const cols = [
      { key: "name", label: "Name" },
      { key: "status", label: "Status", render: (val) => val.toUpperCase() },
    ];
    render(<Table columns={cols} data={data} />);
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("INACTIVE")).toBeInTheDocument();
  });
});
