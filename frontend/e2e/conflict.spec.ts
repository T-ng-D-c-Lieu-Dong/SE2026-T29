import { expect, test } from "@playwright/test";
import {
  dateInBookingZone,
  fillBookingForm,
  openDay,
  slotList,
  submitBooking,
  uniqueName,
} from "./helpers";

test("hai người đặt cùng một slot: người thứ hai nhận thông báo xung đột", async ({ browser }) => {
  const date = dateInBookingZone(5);
  const firstContext = await browser.newContext();
  const secondContext = await browser.newContext();
  const firstPage = await firstContext.newPage();
  const secondPage = await secondContext.newPage();

  try {
    await openDay(firstPage, date);
    await openDay(secondPage, date);

    const slotLabel = (await slotList(firstPage).getByRole("button").first().innerText()).trim();
    expect(slotLabel.length).toBeGreaterThan(0);

    await slotList(firstPage).getByRole("button", { name: slotLabel, exact: true }).click();
    await slotList(secondPage).getByRole("button", { name: slotLabel, exact: true }).click();

    await fillBookingForm(firstPage, uniqueName("E2E Người thứ nhất"));
    await submitBooking(firstPage);
    await expect(firstPage.getByRole("status")).toContainText("Đặt lịch thành công.");

    await fillBookingForm(secondPage, uniqueName("E2E Người thứ hai"));
    await submitBooking(secondPage);

    const alert = secondPage.getByRole("alert");
    await expect(alert).toContainText("Slot đã có người đặt");
    await expect(secondPage.getByRole("status")).toHaveCount(0);
  } finally {
    await firstContext.close();
    await secondContext.close();
  }
});
