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

test("huỷ một lịch đã đặt qua hộp thoại xác nhận", async ({ page }) => {
  const customerName = uniqueName("E2E Huỷ lịch");

  await openDay(page, dateInBookingZone(4));
  const slot = slotList(page).getByRole("button").first();
  const slotLabel = (await slot.innerText()).trim();
  await slot.click();
  await fillBookingForm(page, customerName);
  await submitBooking(page);
  await expect(page.getByRole("status")).toContainText("Đặt lịch thành công.");

  const row = await findAppointmentRow(page, customerName);
  await row.getByRole("button", { name: `Huỷ lịch của ${customerName}` }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Xác nhận huỷ" }).click();

  await expect(page.getByRole("status")).toContainText("Đã huỷ lịch.");
  await expect(slotList(page).getByRole("button", { name: slotLabel, exact: true })).toBeVisible();
  const updatedRow = await findAppointmentRow(page, customerName);
  await expect(updatedRow).toContainText("Đã huỷ");
});
