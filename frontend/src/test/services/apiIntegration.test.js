import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock api module
vi.mock("../../services/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import api from "../../services/api";
import { getBookings, getBooking, createBooking } from "../../services/bookingService";
import { getTasks, getTask, assignTask, completeTask } from "../../services/cleaningService";
import { getSalaries } from "../../services/salaryService";

describe("API service layer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("bookingService", () => {
    it("getBookings calls correct endpoint with params", async () => {
      api.get.mockResolvedValue({ data: { results: [] } });
      const result = await getBookings({ status: "active" });
      expect(api.get).toHaveBeenCalledWith("/bookings/bookings/", { params: { status: "active" } });
      expect(result).toEqual({ results: [] });
    });

    it("getBooking fetches a single booking by id", async () => {
      const booking = { id: 5, room: 1, status: "active" };
      api.get.mockResolvedValue({ data: booking });
      const result = await getBooking(5);
      expect(api.get).toHaveBeenCalledWith("/bookings/bookings/5/");
      expect(result).toEqual(booking);
    });

    it("createBooking posts booking data", async () => {
      const newBooking = { room: 1, check_in_date: "2026-04-10" };
      api.post.mockResolvedValue({ data: { id: 1, ...newBooking } });
      const result = await createBooking(newBooking);
      expect(api.post).toHaveBeenCalledWith("/bookings/bookings/", newBooking);
      expect(result.id).toBe(1);
    });

    it("getBookings propagates API errors", async () => {
      const err = new Error("Network Error");
      api.get.mockRejectedValue(err);
      await expect(getBookings()).rejects.toThrow("Network Error");
    });
  });

  describe("cleaningService", () => {
    it("getTasks calls correct endpoint", async () => {
      api.get.mockResolvedValue({ data: { results: [] } });
      const result = await getTasks({ status: "pending" });
      expect(api.get).toHaveBeenCalledWith("/cleaning/tasks/", { params: { status: "pending" } });
      expect(result).toEqual({ results: [] });
    });

    it("getTask fetches a single task", async () => {
      const task = { id: 3, room: "101", status: "assigned" };
      api.get.mockResolvedValue({ data: task });
      const result = await getTask(3);
      expect(api.get).toHaveBeenCalledWith("/cleaning/tasks/3/");
      expect(result).toEqual(task);
    });

    it("assignTask posts with staff id", async () => {
      api.post.mockResolvedValue({ data: { id: 1, assigned_to: 5 } });
      const result = await assignTask(1, 5);
      expect(api.post).toHaveBeenCalledWith("/cleaning/tasks/1/assign/", { assigned_to: 5 });
      expect(result.assigned_to).toBe(5);
    });

    it("assignTask posts empty body for self-assign", async () => {
      api.post.mockResolvedValue({ data: { id: 1 } });
      await assignTask(1);
      expect(api.post).toHaveBeenCalledWith("/cleaning/tasks/1/assign/", {});
    });

    it("completeTask posts to complete endpoint", async () => {
      api.post.mockResolvedValue({ data: { id: 1, status: "completed" } });
      const result = await completeTask(1);
      expect(api.post).toHaveBeenCalledWith("/cleaning/tasks/1/complete/");
      expect(result.status).toBe("completed");
    });

    it("getTasks propagates API errors", async () => {
      api.get.mockRejectedValue(new Error("500 Internal"));
      await expect(getTasks()).rejects.toThrow("500 Internal");
    });
  });

  describe("salaryService", () => {
    it("getSalaries calls correct endpoint", async () => {
      api.get.mockResolvedValue({ data: { results: [{ id: 1, amount: 1000 }] } });
      const result = await getSalaries({ month: 4 });
      expect(api.get).toHaveBeenCalledWith("/salary/", { params: { month: 4 } });
      expect(result.results[0].amount).toBe(1000);
    });

    it("getSalaries defaults to empty params", async () => {
      api.get.mockResolvedValue({ data: [] });
      await getSalaries();
      expect(api.get).toHaveBeenCalledWith("/salary/", { params: {} });
    });
  });
});
