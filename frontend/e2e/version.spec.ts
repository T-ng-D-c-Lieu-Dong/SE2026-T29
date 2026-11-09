import { expect, test } from "@playwright/test";

test("footer hiển thị đúng release và commit đang chạy", async ({ page, request }) => {
  const response = await request.get("/api/version");
  expect(response.ok()).toBeTruthy();
  const version = (await response.json()) as {
    release: string;
    commit_sha: string;
    environment?: string;
  };

  await page.goto("/");
  const footer = page.getByTestId("version-footer");

  await expect(footer).toContainText(`Release ${version.release}`);
  await expect(footer).toContainText(`Commit ${version.commit_sha.slice(0, 7)}`);

  const badge = page.locator(".env-badge");
  if (version.environment) {
    await expect(badge).toContainText(version.environment);
  } else {
    await expect(badge).toHaveCount(0);
  }
});
