import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConflictError } from "../api/client";
import type { Appointment, AppointmentList } from "../types";
import { BookingPage } from "./BookingPage";
import * as api from "../api/appointments";

vi.mock("../api/appointments", () => ({
  fetchSlots: vi.fn(),
  listAppointments: vi.fn(),
  createAppointment: vi.fn(),
  cancelAppointment: vi.fn(),
  fetchVersion: vi.fn(),
}));

const mocked = vi.mocked(api);

const MORNING_SLOT = "2026-10-27T08:00:00+07:00";

const bookedAppointment: Appointment = {
  id: "11111111-1111-1111-1111-111111111111",
  customer_name: "Nguyễn An",
  starts_at: MORNING_SLOT,
  status: "booked",
  created_at: "2026-10-22T03:00:00+00:00",
  cancelled_at: null,
};

const emptyList: AppointmentList = { items: [], total: 0, limit: 20, offset: 0 };

function renderPage(): void {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <BookingPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocked.fetchSlots.mockResolvedValue([{ starts_at: MORNING_SLOT }]);
  mocked.listAppointments.mockResolvedValue(emptyList);
  mocked.fetchVersion.mockResolvedValue({ release: "v0.1.0", commit_sha: "abcdef1234567" });
  mocked.cancelAppointment.mockResolvedValue(undefined);
});

describe("BookingPage", () => {
  it("renders available slots in Asia/Ho_Chi_Minh", async () => {
    renderPage();

    expect(await screen.findByRole("button", { name: "08:00" })).toBeInTheDocument();
  });

  it("shows a loading state while slots are loading", async () => {
    mocked.fetchSlots.mockReturnValue(new Promise(() => undefined));
    renderPage();

    expect(await screen.findByText("Đang tải slot trống…")).toBeInTheDocument();
  });

  it("shows an empty state when the day has no slots", async () => {
    mocked.fetchSlots.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Không còn slot trống cho ngày này.")).toBeInTheDocument();
  });

  it("shows an error state and retries the request", async () => {
    mocked.fetchSlots
      .mockRejectedValueOnce(new Error("Mất kết nối tới máy chủ"))
      .mockResolvedValue([{ starts_at: MORNING_SLOT }]);
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Mất kết nối tới máy chủ")).toBeInTheDocument();

    await userEvent.click(within(alert).getByRole("button", { name: "Thử lại" }));

    expect(await screen.findByRole("button", { name: "08:00" })).toBeInTheDocument();
    expect(mocked.fetchSlots).toHaveBeenCalledTimes(2);
  });

  it("books the selected slot and shows a success message", async () => {
    mocked.createAppointment.mockResolvedValue(bookedAppointment);
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "08:00" }));
    await userEvent.type(screen.getByLabelText("Tên khách hàng"), "Nguyễn An");
    await userEvent.click(screen.getByRole("button", { name: "Đặt lịch" }));

    await waitFor(() => {
      expect(mocked.createAppointment).toHaveBeenCalledWith({
        customer_name: "Nguyễn An",
        starts_at: MORNING_SLOT,
      });
    });
    expect(await screen.findByText("Đặt lịch thành công.")).toBeInTheDocument();
    expect(screen.getByLabelText("Tên khách hàng")).toHaveValue("");
  });

  it("refreshes slots and appointments after a successful booking", async () => {
    mocked.createAppointment.mockResolvedValue(bookedAppointment);
    renderPage();

    await screen.findByRole("button", { name: "08:00" });
    await waitFor(() => {
      expect(mocked.fetchSlots).toHaveBeenCalledTimes(1);
      expect(mocked.listAppointments).toHaveBeenCalledTimes(1);
    });

    await userEvent.click(screen.getByRole("button", { name: "08:00" }));
    await userEvent.type(screen.getByLabelText("Tên khách hàng"), "Nguyễn An");
    await userEvent.click(screen.getByRole("button", { name: "Đặt lịch" }));

    expect(await screen.findByText("Đặt lịch thành công.")).toBeInTheDocument();
    await waitFor(() => {
      expect(mocked.fetchSlots).toHaveBeenCalledTimes(2);
      expect(mocked.listAppointments).toHaveBeenCalledTimes(2);
    });
  });

  it("shows the conflict message on 409 and never reports success", async () => {
    mocked.createAppointment.mockRejectedValue(new ConflictError());
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "08:00" }));
    await userEvent.type(screen.getByLabelText("Tên khách hàng"), "Nguyễn An");
    await userEvent.click(screen.getByRole("button", { name: "Đặt lịch" }));

    expect(await screen.findByText("Slot đã có người đặt")).toBeInTheDocument();
    expect(screen.queryByText("Đặt lịch thành công.")).not.toBeInTheDocument();
  });

  it("cancels a booking after confirmation", async () => {
    mocked.listAppointments.mockResolvedValue({
      ...emptyList,
      items: [bookedAppointment],
      total: 1,
    });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Huỷ lịch của Nguyễn An" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Huỷ lịch này?")).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận huỷ" }));

    await waitFor(() => {
      expect(mocked.cancelAppointment).toHaveBeenCalledWith(bookedAppointment.id);
    });
    expect(await screen.findByText("Đã huỷ lịch.")).toBeInTheDocument();
  });

  it("refreshes slots and appointments after cancelling a booking", async () => {
    mocked.listAppointments.mockResolvedValue({
      ...emptyList,
      items: [bookedAppointment],
      total: 1,
    });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Huỷ lịch của Nguyễn An" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận huỷ" }));

    expect(await screen.findByText("Đã huỷ lịch.")).toBeInTheDocument();
    await waitFor(() => {
      expect(mocked.fetchSlots).toHaveBeenCalledTimes(2);
      expect(mocked.listAppointments).toHaveBeenCalledTimes(2);
    });
  });

  it("does not cancel when the confirmation is dismissed", async () => {
    mocked.listAppointments.mockResolvedValue({
      ...emptyList,
      items: [bookedAppointment],
      total: 1,
    });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "Huỷ lịch của Nguyễn An" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Không" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mocked.cancelAppointment).not.toHaveBeenCalled();
  });
});
