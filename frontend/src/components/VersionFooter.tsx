import type { ReactNode } from "react";
import type { VersionInfo } from "../types";

interface EnvironmentBadgeProps {
  environment: string | undefined;
}

export function EnvironmentBadge({ environment }: EnvironmentBadgeProps): ReactNode {
  if (!environment) {
    return null;
  }
  return (
    <span className="env-badge" title="Môi trường triển khai">
      Môi trường: {environment}
    </span>
  );
}

interface VersionFooterProps {
  version: VersionInfo | undefined;
  isLoading: boolean;
  isError: boolean;
}

export function VersionFooter({ version, isLoading, isError }: VersionFooterProps): ReactNode {
  return (
    <footer className="app-footer" data-testid="version-footer">
      {isLoading ? <span>Đang tải phiên bản…</span> : null}
      {!isLoading && (isError || !version) ? <span>Không tải được thông tin phiên bản</span> : null}
      {!isLoading && version ? (
        <>
          <span>
            Release <strong>{version.release}</strong>
          </span>
          <span>
            Commit <strong>{version.commit_sha.slice(0, 7)}</strong>
          </span>
        </>
      ) : null}
    </footer>
  );
}
