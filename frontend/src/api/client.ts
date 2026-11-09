const REQUEST_TIMEOUT_MS = 10_000;
export const RETRY_DELAYS_MS = [300, 900] as const;

export interface ApiErrorInit {
  status: number;
  detail?: string;
  traceId?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: string;
  readonly traceId?: string;

  constructor(message: string, init: ApiErrorInit) {
    super(message);
    this.name = "ApiError";
    this.status = init.status;
    this.detail = init.detail;
    this.traceId = init.traceId;
  }
}

export class ConflictError extends ApiError {
  constructor(traceId?: string) {
    super("Slot đã có người đặt", { status: 409, detail: "slot_already_booked", traceId });
    this.name = "ConflictError";
  }
}

export class NetworkError extends Error {
  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = "NetworkError";
    this.cause = cause;
  }
}

export interface ErrorDescription {
  message: string;
  traceId?: string;
}

export function describeError(error: unknown): ErrorDescription {
  if (error instanceof ApiError) {
    return error.traceId === undefined
      ? { message: error.message }
      : { message: error.message, traceId: error.traceId };
  }
  if (error instanceof Error && error.message) {
    return { message: error.message };
  }
  return { message: "Đã xảy ra lỗi không xác định" };
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

function traceIdFrom(response: Response): string | undefined {
  const header = response.headers.get("traceparent");
  if (!header) {
    return undefined;
  }
  const match = /^[0-9a-f]{2}-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}$/i.exec(header.trim());
  return match?.[1];
}

async function readDetail(response: Response): Promise<string | undefined> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body) {
      const detail: unknown = (body as { detail?: unknown }).detail;
      if (typeof detail === "string") {
        return detail;
      }
    }
    return undefined;
  } catch {
    return undefined;
  }
}

async function performFetch<T>(path: string, init: RequestInit): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  const externalSignal = init.signal;
  const onExternalAbort = () => {
    controller.abort();
  };
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort();
    } else {
      externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }
  }

  try {
    let response: Response;
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }

    try {
      response = await fetch(path, { ...init, headers, signal: controller.signal });
    } catch (error) {
      const timeout = timedOut;
      throw new NetworkError(
        timeout ? "Yêu cầu quá thời gian chờ" : "Không kết nối được tới máy chủ",
        error,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    if (!response.ok) {
      const detail = await readDetail(response);
      const traceId = traceIdFrom(response);
      if (response.status === 409) {
        throw new ConflictError(traceId);
      }
      throw new ApiError(detail ?? `Máy chủ trả về lỗi ${response.status}`, {
        status: response.status,
        ...(detail === undefined ? {} : { detail }),
        ...(traceId === undefined ? {} : { traceId }),
      });
    }

    try {
      return (await response.json()) as T;
    } catch {
      throw new ApiError("Phản hồi không hợp lệ từ máy chủ", { status: response.status });
    }
  } finally {
    clearTimeout(timer);
    externalSignal?.removeEventListener("abort", onExternalAbort);
  }
}

/**
 * Fetch JSON from the API.
 *
 * Only idempotent GET requests are retried, and only for network failures or 5xx
 * responses. Retries use a short, bounded backoff so a failing backend cannot keep
 * the UI waiting indefinitely.
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const maxRetries = method === "GET" ? RETRY_DELAYS_MS.length : 0;
  let attempt = 0;

  for (;;) {
    try {
      return await performFetch<T>(path, init);
    } catch (error) {
      const retryable =
        error instanceof NetworkError || (error instanceof ApiError && error.status >= 500);
      if (!retryable || attempt >= maxRetries) {
        throw error;
      }
      const delay = RETRY_DELAYS_MS[attempt] ?? 0;
      attempt += 1;
      await sleep(delay);
    }
  }
}
