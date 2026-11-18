import { expect, test } from "@playwright/test";

test("API lịch hẹn từ chối request không có identity", async ({ playwright, baseURL }) => {
  const anonymous = await playwright.request.newContext({ baseURL, extraHTTPHeaders: {} });
  try {
    const list = await anonymous.get("/api/appointments");
    expect(list.status()).toBe(401);
    const create = await anonymous.post("/api/appointments", {
      data: { customer_name: "E2E Anonymous", starts_at: "2030-01-01T10:00:00+07:00" },
    });
    expect(create.status()).toBe(401);
  } finally {
    await anonymous.dispose();
  }
});
