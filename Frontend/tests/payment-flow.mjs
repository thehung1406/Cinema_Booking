import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
const base = process.env.UI_BASE_URL || "http://127.0.0.1:5173";
const screenshotDir = process.env.UI_SCREENSHOT_DIR;
if (screenshotDir) await mkdir(screenshotDir, { recursive: true });
let stage = "PROCESSING", review = false, paid = true, ticketRequests = 0, caseRetries = 0;
const errors = [];
const booking = { id: 77, bookingId: 77, filmTitle: "Phim kiểm thử Payment M9", theaterName: "Rạp kiểm thử", roomName: "Phòng 1", showDate: "2026-11-10", startTime: "18:30", seats: [{ seat_id: 1, seat_name: "A1", price: 75000 }], foodItems: [], totalAmount: 75000 };
async function fixture(context) {
  await context.route("**/*", async route => {
    const req = route.request();
    if (!["fetch", "xhr"].includes(req.resourceType())) return route.continue();
    const path = new URL(req.url()).pathname.replace(/^\/api/, "");
    let body = [], status = 200;
    if (path === "/payment/status/77" || path === "/payment/vnpay-return") body = { booking_id: 77, provider_status: paid ? "PAID" : "PENDING", fulfillment_status: stage, requires_review: review, can_retry: !paid };
    else if (path === "/bookings/77") body = { ...booking, bookingStatus: stage === "ISSUED" ? "CONFIRMED" : "PENDING", paymentStatus: paid ? "PAID" : "PENDING" };
    else if (path === "/tickets/booking/77") { ticketRequests++; body = [{ ticket_code: "BOOKING-ISSUED-TICKET-77-A1", status: "ISSUED" }]; }
    else if (path === "/admin/session") body = { user: { username: "admin-fixture", role: "ADMIN" }, permissions: ["reports.view"] };
    else if (path === "/admin/payment-reconciliation") body = { total: 1, items: [{ id: "case-1", payment_id: 88, reason: "BOOKING_REJECTED", reference: "RESERVATION_EXPIRED", created_at: new Date().toISOString() }] };
    else if (path === "/admin/payment-reconciliation/case-1/retry") { assert.equal(req.postDataJSON().reason, "Đã kiểm tra chứng từ provider"); caseRetries++; body = { queued: true }; }
    else if (path === "/payment/vnpay-url") { status = 503; body = { detail: "fixture gateway unavailable" }; }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
}
try {
  const context = await browser.newContext();
  await context.addInitScript(() => localStorage.setItem("userInfo", JSON.stringify({ id: 7, username: "payment-fixture", access_token: "isolated-token", role: "USER" })));
  await fixture(context); const page = await context.newPage(); page.on("pageerror", e => errors.push(e.message));
  for (const width of [375, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    stage = "PROCESSING"; review = false; paid = true;
    await page.goto(`${base}/payment-result?bookingId=77`);
    await page.getByRole("heading", { name: "Đã thu tiền — đang xác nhận vé", exact: true }).waitFor();
    assert.equal(await page.locator('svg[role="img"]').count(), 0);
    stage = "REQUIRES_REVIEW"; review = true;
    await page.getByRole("button", { name: "Kiểm tra lại trạng thái" }).click();
    await page.getByRole("heading", { name: "Giao dịch cần hỗ trợ / đối soát", exact: true }).waitFor();
    assert.equal(await page.getByRole("heading", { name: "Vé điện tử của bạn" }).count(), 0);
    if (screenshotDir) await page.screenshot({ path: resolve(screenshotDir, `payment-review-${width}.png`), fullPage: true });
    stage = "ISSUED";
    await page.getByRole("button", { name: "Kiểm tra lại trạng thái" }).click();
    await page.getByRole("heading", { name: "Vé điện tử của bạn", exact: true }).waitFor();
    await page.getByText("BOOKING-ISSUED-TICKET-77-A1", { exact: true }).waitFor();
    assert.equal(await page.locator('svg[role="img"]').count(), 1);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    if (screenshotDir) await page.screenshot({ path: resolve(screenshotDir, `payment-issued-${width}.png`), fullPage: true });
    stage = "PROCESSING"; await page.goto(`${base}/payment/77`);
    await page.getByRole("heading", { name: "Đã thu tiền — đang xác nhận vé", exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: /^Thanh toán/ }).count(), 0);
  }
  stage = "AWAITING_PAYMENT"; paid = false; review = false;
  await page.goto(`${base}/payment/77`);
  await page.getByRole("heading", { name: "Hoàn tất đơn vé", exact: true }).waitFor();
  await page.getByRole("button", { name: /^Thanh toán/ }).click();
  await page.getByRole("alert").filter({ hasText: "fixture gateway unavailable" }).waitFor();
  assert.equal(await page.getByRole("heading", { name: "Hoàn tất đơn vé", exact: true }).count(), 1);
  await page.goto(`${base}/admin/payment-reconciliation`);
  await page.getByRole("heading", { name: "Đối soát thanh toán", exact: true }).waitFor();
  await page.getByRole("button", { name: "Thử xác nhận lại #88", exact: true }).click();
  assert.equal(await page.getByRole("button", { name: "Ghi nhận lý do và thử lại", exact: true }).isDisabled(), true);
  await page.getByLabel("Lý do thử xác nhận giao dịch #88").fill("Đã kiểm tra chứng từ provider");
  await page.getByRole("button", { name: "Ghi nhận lý do và thử lại", exact: true }).click();
  await page.getByRole("status").filter({ hasText: "tiền chưa được hoàn" }).waitFor();
  assert.equal(caseRetries, 1);
  if (screenshotDir) await page.screenshot({ path: resolve(screenshotDir, "payment-reconciliation.png"), fullPage: true });
  const guest = await browser.newContext(); await fixture(guest);
  const gp = await guest.newPage(); stage = "ISSUED"; paid = true;
  const before = ticketRequests;
  await gp.goto(`${base}/payment-result?vnp_TxnRef=ref&vnp_SecureHash=fixture-signed-return`);
  await gp.getByRole("heading", { name: "Thanh toán thành công", exact: true }).waitFor();
  assert.equal(await gp.locator('svg[role="img"]').count(), 0);
  assert.equal(ticketRequests, before, "Guest signed return must not fetch protected tickets");
  assert.deepEqual(errors, []);
  console.log("Payment UI passed: paid processing/review/issued, real ticket code only, duplicate charge prevention, guest privacy, audited reconciliation, 375/1440px.");
} finally { await browser.close(); }
