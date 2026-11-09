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

test("@smoke cổng vào UI sống và luồng đặt/huỷ hoạt động sau deploy", async ({ page, request }) => {
  const versionResponse = await request.get("/api/version");
  expect(versionResponse.ok()).toBeTruthy();

  await openDay(page, dateInBookingZone(6));
  await expect(page.getByTestId("version-footer")).toContainText("Release");

  const customerName = uniqueName("E2E Smoke");
  await slotList(page).getByRole("button").first().click();
  await fillBookingForm(page, customerName);
  await submitBooking(page);
  await expect(page.getByRole("status")).toContainText("Đặt lịch thành công.");

  const row = await findAppointmentRow(page, customerName);
  await row.getByRole("button", { name: `Huỷ lịch của ${customerName}` }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Xác nhận huỷ" }).click();
  await expect(page.getByRole("status")).toContainText("Đã huỷ lịch.");
});
