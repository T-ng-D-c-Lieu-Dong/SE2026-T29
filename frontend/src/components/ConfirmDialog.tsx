import { useEffect, useRef, type ReactNode } from "react";
import type { Appointment } from "../types";
import { formatDateTime } from "../time";

interface ConfirmDialogProps {
  appointment: Appointment | null;
  isPending: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  appointment,
  isPending,
  onConfirm,
  onCancel,
}: ConfirmDialogProps): ReactNode {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (appointment) {
      confirmRef.current?.focus();
    }
  }, [appointment]);

  if (!appointment) {
    return null;
  }

  return (
    <div
      className="dialog-overlay"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onCancel();
        }
      }}
    >
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-description"
      >
        <h2 id="confirm-dialog-title">Huỷ lịch này?</h2>
        <p id="confirm-dialog-description">
          Lịch của <strong>{appointment.customer_name}</strong> lúc{" "}
          <strong>{formatDateTime(appointment.starts_at)}</strong> sẽ được đánh dấu là đã huỷ. Slot
          này sẽ trống trở lại.
        </p>
        <div className="dialog__actions">
          <button type="button" className="button button--ghost" onClick={onCancel}>
            Không
          </button>
          <button
            ref={confirmRef}
            type="button"
            className="button button--danger"
            disabled={isPending}
            onClick={onConfirm}
          >
            {isPending ? "Đang huỷ…" : "Xác nhận huỷ"}
          </button>
        </div>
      </div>
    </div>
  );
}
