import type { ComponentProps } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { AppointmentList as AppointmentListData } from "../types";
import { AppointmentList } from "./AppointmentList";

const page: AppointmentListData = {
  items: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      customer_name: "Nguyễn An",
      starts_at: "2026-10-27T08:00:00+07:00",
      status: "booked",
      created_at: "2026-10-22T03:00:00+00:00",
      cancelled_at: null,
    },
  ],
  total: 45,
  limit: 20,
  offset: 0,
};

function renderList(overrides: Partial<ComponentProps<typeof AppointmentList>> = {}): void {
  render(
    <AppointmentList
      data={page}
      isLoading={false}
      error={null}
      page={0}
      pageSize={20}
      onPageChange={vi.fn()}
      onRequestCancel={vi.fn()}
      onRetry={vi.fn()}
      {...overrides}
    />,
  );
}

describe("AppointmentList", () => {
  it("shows the current page and total returned by the API", () => {
    renderList();

    expect(screen.getByText("Trang 1/3 · 45 lịch")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Trang trước" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Trang sau" })).toBeEnabled();
  });

  it("requests the next page", async () => {
    const onPageChange = vi.fn();
    renderList({ onPageChange });

    await userEvent.click(screen.getByRole("button", { name: "Trang sau" }));

    expect(onPageChange).toHaveBeenCalledWith(1);
  });

  it("requests the previous page and disables forward navigation on the last page", async () => {
    const onPageChange = vi.fn();
    renderList({ page: 2, onPageChange });

    expect(screen.getByText("Trang 3/3 · 45 lịch")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Trang sau" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Trang trước" }));

    expect(onPageChange).toHaveBeenCalledWith(1);
  });

  it("asks for confirmation before cancelling a booked appointment", async () => {
    const onRequestCancel = vi.fn();
    renderList({ onRequestCancel });

    const row = screen.getByRole("row", { name: /Nguyễn An/ });
    await userEvent.click(within(row).getByRole("button", { name: "Huỷ lịch của Nguyễn An" }));

    expect(onRequestCancel).toHaveBeenCalledWith(page.items[0]);
  });
});
