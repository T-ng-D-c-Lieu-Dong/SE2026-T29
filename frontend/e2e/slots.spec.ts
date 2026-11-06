import { expect, test } from "@playwright/test";
import { dateInBookingZone, openDay, slotList } from "./helpers";

test("hiển thị danh sách slot trống cho ngày đã chọn", async ({ page }) => {
  await openDay(page, dateInBookingZone(3));

  const slots = slotList(page).getByRole("button");
  await expect(slots.first()).toBeVisible();
  expect(await slots.count()).toBeGreaterThan(0);
});

test("đổi ngày thì tải lại danh sách slot", async ({ page }) => {
  const firstDate = dateInBookingZone(7);
  const secondDate = dateInBookingZone(8);

  await openDay(page, firstDate);
  expect(await slotList(page).getByRole("button").count()).toBeGreaterThan(0);

  const reload = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === "/api/slots" &&
      new URL(response.url()).searchParams.get("date") === secondDate,
  );

  await page.getByLabel("Ngày").fill(secondDate);
  const response = await reload;

  expect(response.ok()).toBeTruthy();
  const expectedSlots = (await response.json()) as { starts_at: string }[];
  expect(expectedSlots.length).toBeGreaterThan(0);
  await expect(slotList(page).getByRole("button")).toHaveCount(expectedSlots.length);
});
