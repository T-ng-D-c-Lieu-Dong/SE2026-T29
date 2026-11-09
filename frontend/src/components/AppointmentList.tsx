import type { ReactNode } from "react";
import type { Appointment, AppointmentList } from "../types";
import type { ErrorDescription } from "../api/client";
import { formatDateTime } from "../time";
import { ErrorBanner } from "./Banners";

interface AppointmentListProps {
  data: AppointmentList | undefined;
  isLoading: boolean;
  error: ErrorDescription | null;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onRequestCancel: (appointment: Appointment) => void;
  onRetry: () => void;
}

function statusLabel(status: Appointment["status"]): string {
  return status === "booked" ? "Đã đặt" : "Đã huỷ";
}

export function AppointmentList({
  data,
  isLoading,
  error,
  page,
  pageSize,
  onPageChange,
  onRequestCancel,
  onRetry,
}: AppointmentListProps): ReactNode {
  if (isLoading) {
    return (
      <p className="muted" role="status">
        Đang tải danh sách lịch…
      </p>
    );
  }

  if (error) {
    return <ErrorBanner message={error.message} traceId={error.traceId} onRetry={onRetry} />;
  }

  if (!data || data.items.length === 0) {
    return <p className="empty">Chưa có lịch nào được đặt.</p>;
  }

  const totalPages = Math.max(1, Math.ceil(data.total / pageSize));

  return (
    <div className="appointment-list">
      <table className="table">
        <caption className="sr-only">Danh sách lịch hẹn</caption>
        <thead>
          <tr>
            <th scope="col">Khách hàng</th>
            <th scope="col">Thời gian</th>
            <th scope="col">Trạng thái</th>
            <th scope="col">
              <span className="sr-only">Thao tác</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((appointment) => (
            <tr key={appointment.id}>
              <td data-label="Khách hàng">
                <span className="cell-strong">{appointment.customer_name}</span>
                <span className="cell-meta">Tạo lúc {formatDateTime(appointment.created_at)}</span>
              </td>
              <td data-label="Thời gian">{formatDateTime(appointment.starts_at)}</td>
              <td data-label="Trạng thái">
                <span className={`badge badge--${appointment.status}`}>
                  {statusLabel(appointment.status)}
                </span>
              </td>
              <td className="table__actions">
                {appointment.status === "booked" ? (
                  <button
                    type="button"
                    className="button button--danger-ghost"
                    aria-label={`Huỷ lịch của ${appointment.customer_name}`}
                    onClick={() => {
                      onRequestCancel(appointment);
                    }}
                  >
                    Huỷ lịch
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <nav className="pagination" aria-label="Phân trang danh sách lịch">
        <button
          type="button"
          className="button button--ghost"
          disabled={page === 0}
          onClick={() => {
            onPageChange(page - 1);
          }}
        >
          Trang trước
        </button>
        <span className="pagination__status">
          Trang {page + 1}/{totalPages} · {data.total} lịch
        </span>
        <button
          type="button"
          className="button button--ghost"
          disabled={page + 1 >= totalPages}
          onClick={() => {
            onPageChange(page + 1);
          }}
        >
          Trang sau
        </button>
      </nav>
    </div>
  );
}
