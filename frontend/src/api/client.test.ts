import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError, ConflictError, NetworkError, RETRY_DELAYS_MS } from "./client";

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function abortableFetch(): typeof fetch {
  return vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
    return new Promise<Response>((_resolve, reject) => {
      const signal = init?.signal;
      signal?.addEventListener("abort", () => {
        reject(new DOMException("Aborted", "AbortError"));
      });
    });
  }) as unknown as typeof fetch;
}

describe("apiFetch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("maps HTTP 409 to ConflictError with the server detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "slot taken" }, 409)));

    await expect(apiFetch("/api/appointments", { method: "POST" })).rejects.toBeInstanceOf(
      ConflictError,
    );
  });

  it("exposes the trace id from the traceparent response header", async () => {
    const traceId = "4bf92f3577b34da6a3ce929d0e0e4736";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "boom" }, 500, {
          traceparent: `00-${traceId}-00f067aa0ba902b7-01`,
        }),
      ),
    );

    const error = await apiFetch("/api/appointments", { method: "POST" }).catch(
      (reason: unknown) => reason,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).traceId).toBe(traceId);
    expect((error as ApiError).status).toBe(500);
  });

  it("retries idempotent GET requests on network errors with bounded backoff", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockResolvedValueOnce(jsonResponse({ release: "v1" }));
    vi.stubGlobal("fetch", fetchMock);

    const request = apiFetch<{ release: string }>("/api/version");
    const settled = expect(request).resolves.toEqual({ release: "v1" });

    await vi.advanceTimersByTimeAsync(RETRY_DELAYS_MS[0]);
    await vi.advanceTimersByTimeAsync(RETRY_DELAYS_MS[1]);
    await settled;

    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("never retries POST requests", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("network down"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      apiFetch("/api/appointments", { method: "POST", body: JSON.stringify({}) }),
    ).rejects.toBeInstanceOf(NetworkError);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reports a timeout as NetworkError when the request hangs", async () => {
    vi.stubGlobal("fetch", abortableFetch());

    const request = apiFetch("/api/appointments", { method: "POST" });
    const settled = expect(request).rejects.toMatchObject({
      name: "NetworkError",
      message: "Yêu cầu quá thời gian chờ",
    });

    await vi.advanceTimersByTimeAsync(10_000);
    await settled;
  });

  it("returns undefined for 204 responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    await expect(apiFetch("/api/appointments/abc", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
