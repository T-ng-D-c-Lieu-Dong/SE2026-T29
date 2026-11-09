import type { ReactNode } from "react";
import type { Slot } from "../types";
import { formatDateTime, formatTime } from "../time";
import type { ErrorDescription } from "../api/client";
import { ErrorBanner } from "./Banners";

interface SlotListProps {
  slots: Slot[] | undefined;
  isLoading: boolean;
  error: ErrorDescription | null;
  selectedSlot: string | null;
  disabled: boolean;
  onSelect: (startsAt: string) => void;
  onRetry: () => void;
}

export function SlotList({
  slots,
  isLoading,
  error,
  selectedSlot,
  disabled,
  onSelect,
  onRetry,
}: SlotListProps): ReactNode {
  if (isLoading) {
    return (
      <p className="muted" role="status">
        Đang tải slot trống…
      </p>
    );
  }

  if (error) {
    return <ErrorBanner message={error.message} traceId={error.traceId} onRetry={onRetry} />;
  }

  if (!slots || slots.length === 0) {
    return <p className="empty">Không còn slot trống cho ngày này.</p>;
  }

  return (
    <ul className="slot-grid" aria-label="Slot trống">
      {slots.map((slot) => {
        const selected = slot.starts_at === selectedSlot;
        return (
          <li key={slot.starts_at}>
            <button
              type="button"
              className="slot"
              aria-pressed={selected}
              title={formatDateTime(slot.starts_at)}
              disabled={disabled}
              onClick={() => {
                onSelect(slot.starts_at);
              }}
            >
              {formatTime(slot.starts_at)}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
