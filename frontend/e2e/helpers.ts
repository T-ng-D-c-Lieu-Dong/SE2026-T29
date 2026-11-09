import { expect, type Locator, type Page } from "@playwright/test";

export const BOOKING_TIME_ZONE = "Asia/Ho_Chi_Minh";

/** Calendar date (YYYY-MM-DD) a number of days from now, in the booking timezone. */
export function dateInBookingZone(offsetDays: number): string {
  const target = new Date(Date.now() + offsetDays * 24 * 60 * 60 * 1000);
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: BOOKING_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(target);
}

export function uniqueName(prefix: string): string {
  return `${prefix} ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export function slotList(page: Page): Locator {
  return page.getByRole("list", { name: "Slot trống" });
}

export async function openDay(page: Page, date: string): Promise<void> {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Đặt lịch hẹn" })).toBeVisible();
  await page.getByLabel("Ngày").fill(date);
  await expect(slotList(page)).toBeVisible();
}

export async function fillBookingForm(page: Page, customerName: string): Promise<void> {
  await page.getByLabel("Tên khách hàng").fill(customerName);
}

export async function submitBooking(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Đặt lịch", exact: true }).click();
}

/** Finds an appointment row, following pagination until it appears. */
export async function findAppointmentRow(page: Page, customerName: string): Promise<Locator> {
  const row = page.getByRole("row").filter({ hasText: customerName });
  const nextButton = page.getByRole("button", { name: "Trang sau" });

  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (
      await row
        .first()
        .isVisible()
        .catch(() => false)
    ) {
      return row.first();
    }
    if (!(await nextButton.isEnabled().catch(() => false))) {
      break;
    }
    await nextButton.click();
    await page.waitForTimeout(150);
  }

  await expect(row.first()).toBeVisible();
  return row.first();
}
