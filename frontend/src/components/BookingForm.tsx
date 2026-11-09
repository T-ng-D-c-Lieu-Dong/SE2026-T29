import type { ReactNode } from "react";
import { formatDateTime } from "../time";

interface BookingFormProps {
  selectedSlot: string | null;
  customerName: string;
  isPending: boolean;
  onNameChange: (value: string) => void;
  onSubmit: () => void;
}

export function BookingForm({
  selectedSlot,
  customerName,
  isPending,
  onNameChange,
  onSubmit,
}: BookingFormProps): ReactNode {
  const canSubmit = selectedSlot !== null && customerName.trim().length > 0 && !isPending;

  return (
    <form
      className="booking-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) {
          onSubmit();
        }
      }}
    >
      <h3 className="booking-form__title">Thông tin đặt lịch</h3>
      <p className="booking-form__slot">
        Slot đã chọn:{" "}
        <strong>{selectedSlot ? formatDateTime(selectedSlot) : "chưa chọn slot nào"}</strong>
      </p>
      <label className="field">
        <span>Tên khách hàng</span>
        <input
          type="text"
          name="customer_name"
          value={customerName}
          maxLength={100}
          required
          autoComplete="name"
          placeholder="Ví dụ: Nguyễn An"
          onChange={(event) => {
            onNameChange(event.target.value);
          }}
        />
      </label>
      <button type="submit" className="button button--primary" disabled={!canSubmit}>
        {isPending ? "Đang đặt…" : "Đặt lịch"}
      </button>
    </form>
  );
}
