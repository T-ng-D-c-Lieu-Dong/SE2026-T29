import { expect, test } from "@playwright/test";
import {
  dateInBookingZone,
  fillBookingForm,
  findAppointmentRow,
  openDay,
  slotList,
  submitBooking,
  uniqueName,
} from "./helpers";

test("đặt một slot và thấy lịch trong danh sách", async ({ page }) => {
  const customerName = uniqueName("E2E Đặt lịch");

  await openDay(page, dateInBookingZone(3));
  const slot = slotList(page).getByRole("button").first();
  const slotLabel = (await slot.innerText()).trim();
  await slot.click();
  await fillBookingForm(page, customerName);
  await submitBooking(page);

  await expect(page.getByRole("status")).toContainText("Đặt lịch thành công.");
  await expect(slotList(page).getByRole("button", { name: slotLabel, exact: true })).toHaveCount(0);

  const row = await findAppointmentRow(page, customerName);
  await expect(row).toContainText("Đã đặt");
});

test("báo lỗi khi chưa chọn slot", async ({ page }) => {
  await openDay(page, dateInBookingZone(3));
  await fillBookingForm(page, uniqueName("E2E Chưa chọn"));

  await expect(page.getByRole("button", { name: "Đặt lịch", exact: true })).toBeDisabled();
});
