import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({ headless: true,
  ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
const context = await browser.newContext();
await context.addInitScript(() => localStorage.setItem("userInfo", JSON.stringify({
  id: 7, username: "food-test", access_token: "fixture-token", role: "USER" })));
const page = await context.newPage();
const errors = [];
const calls = [];
let menuFailure = false;
let expired = false;
let failCreate = false;
let booking;
const menu = [
  { id: 1, category: "POPCORN", name: "Bỏng ngọt lớn", description: "Bỏng ngọt cỡ lớn", price: "55000", components: [] },
  { id: 3, category: "DRINK", name: "Nước ngọt lớn", description: "Ly nước cỡ lớn", price: "35000", components: [] },
  { id: 6, category: "COMBO", name: "Combo hai người", description: "1 bỏng + 2 nước", price: "110000",
    components: [{ food_item_id: 1, name: "Bỏng ngọt lớn", quantity: 1 }, { food_item_id: 3, name: "Nước ngọt lớn", quantity: 2 }] },
];
page.on("pageerror", e => errors.push(e.message));
await context.route("**/*", async route => {
  const req = route.request();
  if (!["fetch", "xhr"].includes(req.resourceType())) return route.continue();
  const path = new URL(req.url()).pathname.replace(/^\/api/, "");
  let body = [], status = 200;
  if (path === "/food-items") {
    body = menu; if (menuFailure) { status = 503; body = { detail: "Menu unavailable" }; }
  } else if (path === "/seats/showtime/11") body = [{
    seat_id: 3, seat_name: "A3", seat_type: "VIP", price: 120000,
    status: "HOLD", is_held_by_me: true,
    hold_expired_at: new Date(Date.now() + (expired ? -10000 : 600000)).toISOString(),
  }];
  else if (path === "/bookings" && req.method() === "POST") {
    const payload = req.postDataJSON(); calls.push(payload);
    if (failCreate) { status = 400; body = { detail: "Tổng tiền không khớp, vui lòng kiểm tra lại" }; }
    else {
      const foods = payload.foodItems.map(selection => {
        const item = menu.find(i => i.id === selection.food_item_id);
        return { food_item_id: item.id, name: item.name, category: item.category,
          quantity: selection.quantity, unit_price: item.price,
          line_total: Number(item.price) * selection.quantity, components: item.components };
      });
      assert.equal(payload.totalAmount, 120000 + foods.reduce((sum, item) => sum + item.line_total, 0));
      booking = { id: 77, bookingId: 77, filmTitle: "Phim kiểm thử", theaterName: "Rạp", roomName: "Phòng 1",
        showDate: "2026-10-15", startTime: "18:30", seats: [{ seat_id: 3, seat_name: "A3", price: 120000 }],
        totalAmount: payload.totalAmount, foodItems: foods, paymentStatus: "PENDING", bookingStatus: "PENDING" };
      body = { bookingId: 77 };
    }
  } else if (path === "/bookings/77") body = booking;
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
});
const base = process.env.UI_BASE_URL || "http://127.0.0.1:5173";
const screenshotDir = process.env.UI_SCREENSHOT_DIR;
if (screenshotDir) await mkdir(screenshotDir, { recursive: true });
const openFood = async () => {
  await page.goto(`${base}/food-selection/11`);
  await page.getByRole("heading", { name: "Combo hai người", exact: true }).waitFor();
};
try {
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await openFood();
    assert.equal(calls.length, 0);
    await page.getByRole("button", { name: "Thêm Combo hai người", exact: true }).click();
    await page.getByRole("button", { name: "Thêm Combo hai người", exact: true }).click();
    await page.getByRole("button", { name: "Giảm Combo hai người", exact: true }).click();
    assert.equal(await page.getByLabel("Số lượng Combo hai người").innerText(), "1");
    await page.getByRole("button", { name: "Nước", exact: true }).click();
    await page.getByRole("button", { name: "Thêm Nước ngọt lớn", exact: true }).click();
    assert.match(await page.locator("aside.booking-summary").innerText(), /265[.,]000/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    assert.equal(await page.locator("button:visible").evaluateAll(buttons =>
      buttons.filter(b => b.getBoundingClientRect().height < 43.9).length), 0);
    if (screenshotDir) await page.screenshot({ path: resolve(screenshotDir, `food-${width}.png`), fullPage: true });
    // Reset between layout scenarios so no order is submitted until the final one.
  }
  await page.getByRole("button", { name: "Tiếp tục thanh toán", exact: true }).click();
  await page.getByRole("heading", { name: "Hoàn tất đơn vé", exact: true }).waitFor();
  assert.deepEqual(calls.pop().foodItems, [{ food_item_id: 3, quantity: 1 }, { food_item_id: 6, quantity: 1 }]);
  assert.match(await page.locator("body").innerText(), /Mỗi combo: 1 × Bỏng ngọt lớn \+ 2 × Nước ngọt lớn/);

  await openFood();
  await page.getByRole("button", { name: "Thêm Combo hai người", exact: true }).click();
  await page.getByRole("button", { name: "Bỏ qua, chỉ mua vé", exact: true }).click();
  await page.getByRole("heading", { name: "Hoàn tất đơn vé", exact: true }).waitFor();
  assert.deepEqual(calls.pop().foodItems, []);
  assert.equal(booking.totalAmount, 120000);

  failCreate = true;
  await openFood();
  await page.getByRole("button", { name: "Thêm Combo hai người", exact: true }).click();
  await page.getByRole("button", { name: "Tiếp tục thanh toán", exact: true }).click();
  await page.getByRole("alert").filter({ hasText: "Tổng tiền không khớp" }).waitFor();
  await page.getByRole("heading", { name: "Combo hai người", exact: true }).waitFor();
  assert.equal(await page.getByLabel("Số lượng Combo hai người").innerText(), "1");
  calls.pop(); failCreate = false;

  menuFailure = true;
  await page.goto(`${base}/food-selection/11`);
  await page.getByRole("heading", { name: "Chưa tải được thực đơn", exact: true }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Tiếp tục thanh toán", exact: true }).isDisabled(), true);
  await page.getByRole("button", { name: "Bỏ qua, chỉ mua vé", exact: true }).click();
  await page.getByRole("heading", { name: "Hoàn tất đơn vé", exact: true }).waitFor();
  assert.deepEqual(calls.pop().foodItems, []);

  menuFailure = false; expired = true;
  await openFood();
  assert.equal(await page.getByRole("button", { name: "Tiếp tục thanh toán", exact: true }).isDisabled(), true);
  assert.equal(await page.getByRole("button", { name: "Bỏ qua, chỉ mua vé", exact: true }).isDisabled(), true);
  assert.equal(calls.length, 0);
  assert.deepEqual(errors, []);
  console.log("Food flow passed: 3 responsive layouts, mixed combo + drink totals, snapshots, skip, menu failure, server-price retry, expired holds; no browser errors.");
} finally { await browser.close(); }
