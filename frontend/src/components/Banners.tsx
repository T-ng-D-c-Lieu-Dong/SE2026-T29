import type { ReactNode } from "react";

interface ErrorBannerProps {
  message: string;
  traceId?: string;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorBanner({
  message,
  traceId,
  onRetry,
  retryLabel = "Thử lại",
}: ErrorBannerProps): ReactNode {
  return (
    <div className="banner banner--error" role="alert">
      <div className="banner__body">
        <p className="banner__message">{message}</p>
        {traceId ? <p className="banner__meta">Trace: {traceId}</p> : null}
      </div>
      {onRetry ? (
        <button type="button" className="button button--ghost" onClick={onRetry}>
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}

interface StatusBannerProps {
  message: string;
}

export function StatusBanner({ message }: StatusBannerProps): ReactNode {
  return (
    <div className="banner banner--success" role="status">
      <p className="banner__message">{message}</p>
    </div>
  );
}
