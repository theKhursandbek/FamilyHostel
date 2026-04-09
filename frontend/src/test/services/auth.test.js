import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  login,
  logout,
  refreshToken,
  getAccessToken,
  getStoredUser,
  hasToken,
} from "../../services/auth";

// Mock the api module
vi.mock("../../services/api", () => ({
  default: {
    post: vi.fn(),
  },
}));

import api from "../../services/api";

describe("auth service", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe("login", () => {
    it("stores tokens and user data on successful login", async () => {
      const mockResponse = {
        data: {
          access: "access-token-123",
          refresh: "refresh-token-456",
          user: { id: 1, phone: "+998901234567", role: "staff" },
        },
      };
      api.post.mockResolvedValue(mockResponse);

      const result = await login("+998901234567", "password123");

      expect(api.post).toHaveBeenCalledWith("/auth/login/", {
        phone: "+998901234567",
        password: "password123",
      });
      expect(localStorage.setItem).toHaveBeenCalledWith("access_token", "access-token-123");
      expect(localStorage.setItem).toHaveBeenCalledWith("refresh_token", "refresh-token-456");
      expect(result.user.phone).toBe("+998901234567");
    });

    it("throws on failed login", async () => {
      api.post.mockRejectedValue(new Error("Invalid credentials"));
      await expect(login("bad", "bad")).rejects.toThrow("Invalid credentials");
    });
  });

  describe("logout", () => {
    it("clears all stored auth data", () => {
      localStorage.setItem("access_token", "token");
      localStorage.setItem("refresh_token", "refresh");
      localStorage.setItem("user", '{"id":1}');

      logout();

      expect(localStorage.removeItem).toHaveBeenCalledWith("access_token");
      expect(localStorage.removeItem).toHaveBeenCalledWith("refresh_token");
      expect(localStorage.removeItem).toHaveBeenCalledWith("user");
    });
  });

  describe("refreshToken", () => {
    it("refreshes the access token", async () => {
      localStorage.setItem("refresh_token", "old-refresh");
      api.post.mockResolvedValue({ data: { access: "new-access" } });

      const newToken = await refreshToken();

      expect(api.post).toHaveBeenCalledWith("/auth/token/refresh/", { refresh: "old-refresh" });
      expect(newToken).toBe("new-access");
      expect(localStorage.setItem).toHaveBeenCalledWith("access_token", "new-access");
    });

    it("throws when no refresh token is available", async () => {
      await expect(refreshToken()).rejects.toThrow("No refresh token available");
    });

    it("stores rotated refresh token if provided", async () => {
      localStorage.setItem("refresh_token", "old-refresh");
      api.post.mockResolvedValue({
        data: { access: "new-access", refresh: "rotated-refresh" },
      });

      await refreshToken();

      expect(localStorage.setItem).toHaveBeenCalledWith("refresh_token", "rotated-refresh");
    });
  });

  describe("getAccessToken", () => {
    it("returns stored token", () => {
      localStorage.setItem("access_token", "my-token");
      expect(getAccessToken()).toBe("my-token");
    });

    it("returns null when no token", () => {
      expect(getAccessToken()).toBeNull();
    });
  });

  describe("getStoredUser", () => {
    it("returns parsed user object", () => {
      localStorage.setItem("user", '{"id":1,"role":"staff"}');
      const user = getStoredUser();
      expect(user).toEqual({ id: 1, role: "staff" });
    });

    it("returns null when no user stored", () => {
      expect(getStoredUser()).toBeNull();
    });

    it("returns null when stored value is invalid JSON", () => {
      localStorage.setItem("user", "not-json");
      expect(getStoredUser()).toBeNull();
    });
  });

  describe("hasToken", () => {
    it("returns true when token exists", () => {
      localStorage.setItem("access_token", "token");
      expect(hasToken()).toBe(true);
    });

    it("returns false when no token", () => {
      expect(hasToken()).toBe(false);
    });
  });
});
