import { describe, it, expect, vi, beforeEach } from "vitest";
import api from "../../services/api";
import * as authModule from "../../services/auth";

describe("api.js interceptors", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("attaches Authorization header when token exists", () => {
    vi.spyOn(authModule, "getAccessToken").mockReturnValue("my-token");

    const interceptors = api.interceptors.request.handlers;
    const requestHandler = interceptors[0];
    const config = { headers: {} };
    const result = requestHandler.fulfilled(config);

    expect(result.headers.Authorization).toBe("Bearer my-token");
  });

  it("does not attach Authorization header when no token", () => {
    vi.spyOn(authModule, "getAccessToken").mockReturnValue(null);

    const interceptors = api.interceptors.request.handlers;
    const requestHandler = interceptors[0];
    const config = { headers: {} };
    const result = requestHandler.fulfilled(config);

    expect(result.headers.Authorization).toBeUndefined();
  });

  it("has correct base URL", () => {
    expect(api.defaults.baseURL).toBe("http://localhost:8000/api/v1");
  });

  it("has JSON content type", () => {
    expect(api.defaults.headers["Content-Type"]).toBe("application/json");
  });
});
