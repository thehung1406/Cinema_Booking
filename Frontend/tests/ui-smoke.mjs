// Isolated browser fixtures only: every fetch/XHR request is intercepted,
// including an absolute VITE_API_BASE_URL configured by the developer.
// No request from this test reaches a backend or a payment gateway.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { localDateInput } from "../src/utils/formatters.js";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:5173";
const screenshotDir = process.env.UI_SCREENSHOT_DIR;
if (screenshotDir) await mkdir(screenshotDir, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  ...(process.env.BROWSER_EXECUTABLE
    ? { executablePath: process.env.BROWSER_EXECUTABLE }
    : {}),
});
const context = await browser.newContext();
const user = {
  id: 7,
  username: "ui-test",
  full_name: "Người kiểm thử giao diện với tên rất dài",
  email: "ui-test@gmail.com",
  phone: "0900000000",
  access_token: "test-only-token",
  role: "CUSTOMER",
};
await context.addInitScript(
  (value) => localStorage.setItem("userInfo", JSON.stringify(value)),
  user,
);
const date = localDateInput(new Date(Date.now() + 86400000));
const films = [
  {
    id: 1,
    title:
      "Hành trình điện ảnh — Tên phim dài để kiểm tra bố cục trên thiết bị di động",
    image: "/missing-poster.jpg",
    duration: "120 phút",
    genre: "Phiêu lưu, tâm lý",
    rating: "T16",
    release_date: "2025-01-01",
    end_date: "2030-01-01",
    language: "Tiếng Việt",
    subtitle: "Tiếng Việt",
    description:
      "Nội dung kiểm thử bố cục. Đây là dữ liệu riêng trong bài kiểm tra trình duyệt.",
    formats: ["2D"],
    trailer: "about:blank",
  },
  {
    id: 2,
    title: "Phim kiểm thử thứ hai",
    image: "/poster-placeholder.svg",
    duration: "100 phút",
    genre: "Hài",
    release_date: "2025-01-01",
    end_date: "2030-01-01",
  },
  {
    id: 3,
    title: "Phim sắp chiếu kiểm thử",
    image: null,
    release_date: "2099-01-01",
  },
];
const theater = {
  id: 1,
  name: "Rạp kiểm thử giao diện",
  city: "TP. Hồ Chí Minh",
};
const showtime = {
  id: 11,
  film_title: films[0].title,
  theater_name: theater.name,
  room_id: 2,
  room_name: "Phòng 2",
  show_date: date,
  start_time: "18:30:00",
  duration: "120 phút",
  image: "/poster-placeholder.svg",
  format: "2D",
};
let seats = ["A", "B", "C", "D"].flatMap((row, index) =>
  Array.from({ length: 14 }, (_, n) => ({
    seat_id: index * 14 + n + 1,
    seat_name: row + (n + 1),
    seat_type: n === 2 ? "VIP" : row === "D" ? "Couple" : "Standard",
    price: n === 2 ? 120000 : 90000,
    status:
      index === 0 && n === 0
        ? "BOOKED"
        : index === 0 && n === 1
          ? "HOLD"
          : "AVAILABLE",
    is_held_by_me: false,
    hold_expired_at: null,
  })),
);
let booking = {
  id: 77,
  bookingId: 77,
  userId: 7,
  showtimeId: 11,
  filmTitle: films[0].title,
  filmImage: "/missing-poster.jpg",
  theaterName: theater.name,
  roomName: "Phòng 2",
  showDate: date,
  startTime: "18:30:00",
  bookingDate: new Date().toISOString(),
  paymentStatus: "PENDING",
  bookingStatus: "PENDING",
  totalAmount: 120000,
  seats: [{ seat_id: 3, seat_name: "A3", seat_type: "VIP", price: 120000 }],
};
let filmsFail = false,
  filmsEmpty = false,
  bookingFail = false,
  returnState = "success";
const calls = [];
await context.route("**/*", async (route) => {
  const request = route.request();
  if (!["fetch", "xhr"].includes(request.resourceType()))
    return route.continue();
  const url = new URL(request.url());
  const path = url.pathname.replace(/^\/api/, "");
  calls.push({ path, method: request.method(), body: request.postData() });
  let body;
  let status = 200;
  if (path === "/films/") {
    body = filmsEmpty ? [] : films;
    if (filmsFail) {
      status = 503;
      body = { detail: "Test unavailable" };
    }
  } else if (path === "/films/positive-trending") body = [];
  else if (/^\/films\/\d+$/.test(path))
    body = films.find((f) => f.id === Number(path.split("/").pop()));
  else if (path.endsWith("/sentiment-summary"))
    body = {
      total: 0,
      positive: 0,
      neutral: 0,
      negative: 0,
      pending: 0,
      needs_review: 0,
      eligible: false,
      min_reviews: 3,
      window_days: 30,
    };
  else if (path.endsWith("/reviews/mine")) body = null;
  else if (path.endsWith("/reviews")) body = [];
  else if (path.startsWith("/theaters")) body = [theater];
  else if (path === "/showtimes") {
    assert.equal(url.searchParams.get("film_id"), "1");
    assert.equal(url.searchParams.get("theater_id"), "1");
    body = [showtime];
  } else if (path === "/showtimes/11") body = showtime;
  else if (path === "/seats/showtime/11") body = seats;
  else if (["/seats/hold", "/seats/release"].includes(path)) {
    const payload = request.postDataJSON();
    assert.deepEqual(payload, { showtime_id: 11, seat_ids: [3] });
    const holding = path.endsWith("hold");
    seats = seats.map((s) =>
      s.seat_id === 3
        ? {
            ...s,
            status: holding ? "HOLD" : "AVAILABLE",
            is_held_by_me: holding,
            hold_expired_at: holding
              ? new Date(Date.now() + 300000).toISOString()
              : null,
          }
        : s,
    );
    body = holding ? [seats[2]] : { success: true };
  } else if (path === "/bookings" && request.method() === "POST") {
    assert.deepEqual(request.postDataJSON(), {
      userId: 7,
      showtimeId: 11,
      totalAmount: 120000,
      paymentMethod: "Online",
      seats: [{ seat_id: 3, price: 120000 }],
    });
    body = { bookingId: 77 };
  } else if (path === "/bookings") body = [booking];
  else if (path === "/bookings/77") {
    body = booking;
    if (bookingFail) {
      status = 503;
      body = { detail: "Test connection failure" };
    }
  } else if (path === "/payment/vnpay-url") {
    assert.deepEqual(request.postDataJSON(), { bookingId: 77 });
    status = 503;
    body = { detail: "VNPay kiểm thử đang bận" };
  } else if (path === "/payment/vnpay-return") {
    status = returnState === "error" ? 400 : 200;
    body =
      status === 400
        ? { detail: "Chữ ký kiểm thử không hợp lệ" }
        : {
            status: returnState,
            booking:
              returnState === "success"
                ? { ...booking, paymentStatus: "PAID" }
                : null,
            message: "",
          };
  } else if (path === "/user/profile")
    body = { success: true, user: { ...user, full_name: "Tên đã chỉnh sửa" } };
  else if (path === "/auth/login")
    body = { access_token: "test-only-token", token_type: "bearer" };
  else if (path === "/auth/me") body = user;
  else {
    status = 404;
    body = { detail: "Unexpected test endpoint: " + path };
  }
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const results = [];
async function open(path, heading) {
  await page.goto(baseURL + path);
  await page
    .getByRole("heading", { name: heading, exact: true })
    .first()
    .waitFor();
}
async function layout(label, capture = false) {
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
    label + ": page overflow",
  );
  const smallButtons = await page
    .locator("button:visible")
    .evaluateAll((buttons) =>
      buttons
        .filter((b) => b.getBoundingClientRect().height < 43.9)
        .map((b) => b.textContent),
    );
  assert.deepEqual(smallButtons, [], label + ": touch targets");
  const unlabeled = await page
    .locator("button:visible")
    .evaluateAll(
      (buttons) =>
        buttons.filter(
          (b) => !b.textContent.trim() && !b.getAttribute("aria-label"),
        ).length,
    );
  assert.equal(unlabeled, 0, label + ": icon labels");
  if (capture && screenshotDir)
    await page.screenshot({
      path: resolve(screenshotDir, label + ".png"),
      fullPage: true,
    });
  results.push(label);
}
try {
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await open("/", films[0].title);
    await layout("home-" + width, true);
    assert.equal(
      await page.locator(".hero h1").count(),
      1,
      "Only active carousel slide exists",
    );
    await page
      .getByRole("button", { name: "Phim tiếp theo", exact: true })
      .click();
    await page
      .getByRole("heading", { name: films[1].title, exact: true })
      .first()
      .waitFor();
    if (width < 1024) {
      await page.getByRole("button", { name: "Mở menu" }).click();
      await page
        .locator("#mobile-navigation")
        .getByRole("link", { name: "Phim", exact: true })
        .click();
      assert.equal(
        await page.locator("#mobile-navigation").count(),
        0,
        "Menu closes after navigation",
      );
    }
    await open("/movie", "Chọn phim cho buổi hẹn tiếp theo");
    await page.getByLabel("Tìm phim theo tên").fill("Hành trình");
    assert.equal(await page.locator(".movie-card").count(), 1);
    await layout("movies-" + width, true);
    await open("/MovieDetail/1", films[0].title);
    await layout("detail-" + width, true);
    await page.getByRole("button", { name: "Xem trailer" }).click();
    await page.getByRole("dialog").waitFor();
    await page.keyboard.press("Escape");
    assert.equal(
      await page.locator("dialog[open]").count(),
      0,
      "Trailer closes by keyboard",
    );
    await open("/TicketBooking?filmId=1", "Chọn lịch chiếu");
    await page.getByLabel("2. Chọn rạp").selectOption("1");
    await page.getByLabel("3. Chọn ngày").fill(date);
    await page.getByRole("button", { name: /18:30/ }).waitFor();
    await layout("showtimes-" + width, true);
    await open("/seat-selection/11", "Chọn ghế");
    await layout("seats-" + width, true);
    const scroll = await page
      .locator(".seat-scroll")
      .evaluate((el) => ({ width: el.clientWidth, content: el.scrollWidth }));
    if (width === 375)
      assert.ok(
        scroll.content > scroll.width,
        "Seat map scrolls in its own region",
      );
    assert.equal(
      await page.getByRole("button", { name: /^Ghế A1,/ }).isDisabled(),
      true,
    );
    assert.equal(
      await page.getByRole("button", { name: /^Ghế A2,/ }).isDisabled(),
      true,
    );
    await open("/payment/77", "Hoàn tất đơn vé");
    await layout("payment-" + width, true);
    assert.equal(
      await page.getByText(/10 phút|10:00/).count(),
      0,
      "No invented payment deadline",
    );
    await open("/payment-result?bookingId=77", "Đang chờ xác nhận");
    assert.equal(await page.locator('svg[role="img"]').count(), 0);
    await layout("return-pending-" + width);
    await open("/user-info", "Thông tin & đơn vé");
    await page
      .getByRole("link", { name: "Tiếp tục thanh toán", exact: true })
      .waitFor();
    assert.ok(
      (await page.locator("body").innerText()).includes(films[0].title),
    );
    await layout("account-" + width, true);
    await open("/login", "Chào mừng trở lại");
    await layout("login-" + width, true);
    await page.getByRole("button", { name: "Đăng ký tài khoản" }).click();
    await page
      .getByRole("heading", { name: "Tạo tài khoản", exact: true })
      .waitFor();
    await layout("signup-" + width);
  }
  await page.setViewportSize({ width: 375, height: 812 });
  await open("/TicketBooking?filmId=1", "Chọn lịch chiếu");
  await page.getByLabel("2. Chọn rạp").selectOption("1");
  await page.getByLabel("3. Chọn ngày").fill(date);
  await page.getByRole("button", { name: /18:30/ }).click();
  await page.getByRole("button", { name: "Tiếp tục chọn ghế" }).click();
  await page.getByRole("heading", { name: "Chọn ghế", exact: true }).waitFor();
  await page.getByRole("button", { name: /^Ghế A3,/ }).click();
  await page.getByText(/Giữ đến/).waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: /^Ghế A3,/ })
      .getAttribute("aria-pressed"),
    "true",
  );
  await page.getByRole("button", { name: /^Ghế A3,/ }).click();
  assert.equal(
    await page
      .getByRole("button", { name: "Tiếp tục thanh toán", exact: true })
      .isDisabled(),
    true,
  );
  await page.getByRole("button", { name: /^Ghế A3,/ }).click();
  await page
    .getByRole("button", { name: "Tiếp tục thanh toán", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Hoàn tất đơn vé", exact: true })
    .waitFor();
  await page.getByRole("button", { name: /^Thanh toán 120/ }).click();
  await page.getByText("VNPay kiểm thử đang bận", { exact: true }).waitFor();
  assert.equal(
    await page.locator("h2").filter({ hasText: films[0].title }).count(),
    1,
    "Payment error preserves order",
  );
  assert.equal(
    calls.some(
      (c) => c.method === "PATCH" && c.path.includes("payment-status"),
    ),
    false,
    "No client-invented cancellation",
  );

  booking = { ...booking, paymentStatus: "PAID", bookingStatus: "CONFIRMED" };
  await open("/payment-result?bookingId=77", "Thanh toán thành công");
  assert.equal(
    await page.getByRole("heading", { name: "Vé điện tử của bạn" }).count(),
    1,
  );
  await layout("return-success-375", true);
  booking = { ...booking, paymentStatus: "FAILED", bookingStatus: "CANCELLED" };
  await open("/payment-result?bookingId=77", "Thanh toán không thành công");
  assert.equal(
    await page.getByRole("heading", { name: "Vé điện tử của bạn" }).count(),
    0,
  );
  await layout("return-failed-375");
  bookingFail = true;
  await open("/payment-result?bookingId=77", "Chưa xác minh được giao dịch");
  await layout("return-error-375");
  bookingFail = false;
  booking = { ...booking, paymentStatus: "PENDING", bookingStatus: "PENDING" };
  returnState = "error";
  await open(
    "/payment-result?vnp_TxnRef=77&vnp_ResponseCode=00&vnp_SecureHash=test-only-invalid",
    "Chưa xác minh được giao dịch",
  );
  assert.equal(
    await page.getByRole("heading", { name: "Vé điện tử của bạn" }).count(),
    0,
    "Query code alone cannot confirm payment",
  );
  returnState = "success";
  await page.getByRole("button", { name: "Kiểm tra lại trạng thái" }).click();
  await page
    .getByRole("heading", { name: "Thanh toán thành công", exact: true })
    .waitFor();

  await open("/user-info", "Thông tin & đơn vé");
  await page.getByRole("button", { name: "Chỉnh sửa thông tin" }).click();
  await page.getByLabel("Họ và tên").fill("Tên đã chỉnh sửa");
  await page.getByRole("button", { name: "Lưu thông tin" }).click();
  await page
    .getByText("Thông tin tài khoản đã được cập nhật.", { exact: true })
    .waitFor();
  assert.equal(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem("userInfo")).access_token,
    ),
    "test-only-token",
  );

  filmsFail = true;
  await open("/", "Chưa tải được danh sách phim");
  await layout("home-error-375");
  filmsFail = false;
  await page.getByRole("button", { name: "Thử lại", exact: true }).click();
  await page
    .getByRole("heading", { name: films[0].title, exact: true })
    .first()
    .waitFor();
  filmsEmpty = true;
  await open("/", "Một bộ phim. Một trải nghiệm mới.");
  await layout("home-empty-375", true);
  filmsEmpty = false;
  await open("/movie", "Chọn phim cho buổi hẹn tiếp theo");
  await page.getByLabel("Tìm phim theo tên").fill("không có phim này");
  await page
    .getByRole("heading", { name: "Không tìm thấy phim phù hợp" })
    .waitFor();

  await open("/seat-selection/11", "Chọn ghế");
  // Simulate backend expiry, then verify reconciliation without inventing a TTL.
  seats = seats.map((seat) => ({
    ...seat,
    status: seat.seat_id === 3 ? "AVAILABLE" : seat.status,
    is_held_by_me: false,
    hold_expired_at: null,
  }));
  await page.getByRole("button", { name: "Cập nhật", exact: true }).click();
  await page.waitForFunction(
    () =>
      document
        .querySelector('button[aria-label^="Ghế A3,"]')
        ?.getAttribute("aria-pressed") === "false",
  );
  assert.equal(
    await page
      .getByRole("button", { name: /^Ghế A3,/ })
      .getAttribute("aria-pressed"),
    "false",
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Tiếp tục thanh toán", exact: true })
      .isDisabled(),
    true,
  );
  await page.evaluate(() => {
    localStorage.removeItem("userInfo");
    window.dispatchEvent(new Event("loginStatusChanged"));
  });
  await page.getByRole("button", { name: /^Ghế A3,/ }).click();
  await page
    .getByRole("heading", { name: "Chào mừng trở lại", exact: true })
    .waitFor();
  await page.getByLabel("Tên đăng nhập").fill("ui-test");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("test-only-password");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.getByRole("heading", { name: "Chọn ghế", exact: true }).waitFor();
  assert.equal(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem("userInfo")).access_token,
    ),
    "test-only-token",
  );
  await page
    .getByRole("button", { name: "Hỏi trợ lý", exact: true })
    .scrollIntoViewIfNeeded();
  await page.getByRole("button", { name: "Hỏi trợ lý", exact: true }).click();
  await page
    .getByRole("button", { name: "Đóng trợ lý", exact: true })
    .waitFor();
  await layout("assistant-375", true);
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("#cinema-assistant").count(), 0);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open("/movie", "Chọn phim cho buổi hẹn tiếp theo");
  await page
    .getByRole("link", { name: /^Xem chi tiết/ })
    .first()
    .focus();
  assert.notEqual(
    await page
      .locator(":focus")
      .evaluate((el) => getComputedStyle(el).outlineStyle),
    "none",
  );
  assert.equal(
    await page
      .locator(".movie-card")
      .first()
      .evaluate((el) => getComputedStyle(el).transitionDuration),
    "1e-05s",
  );
  assert.deepEqual(errors, [], "No browser runtime errors");
  console.log(
    JSON.stringify(
      {
        passedLayouts: results.length,
        layouts: results,
        checked: [
          "carousel",
          "mobile menu",
          "search",
          "trailer keyboard",
          "hold/release payload",
          "booking payload",
          "VNPay error retry",
          "pending/success/failure/unverified",
          "profile session",
          "API retry",
          "empty",
          "assistant",
          "backend hold reconciliation",
          "login returns to seat selection",
          "focus",
          "reduced motion",
        ],
        browserErrors: errors,
        paymentRequests: "isolated fixtures only",
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
