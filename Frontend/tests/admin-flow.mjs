// Browser contracts use isolated fixtures. No requests reach a real backend.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:5173";
const screenshotDir = process.env.UI_SCREENSHOT_DIR;
if (screenshotDir) await mkdir(screenshotDir, { recursive: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const user = { id: 1, username: "admin-test", full_name: "Quản trị viên kiểm thử", role: "ADMIN", access_token: "isolated-test-token" };
await page.addInitScript((value) => localStorage.setItem("userInfo", JSON.stringify(value)), user);
const permissions = ["films.manage", "rooms.manage", "showtimes.manage", "seat_types.manage", "users.manage", "roles.manage", "knowledge.manage", "reports.view"];
const roles = [{ id: 1, code: "ADMIN", name: "Quản trị viên" }, { id: 2, code: "MANAGER", name: "Quản lý" }, { id: 3, code: "STAFF", name: "Nhân viên" }];
const films = [{ id: 1, title: "Hành trình điện ảnh", duration_minutes: 120, genre_ids: [1], format_ids: [1], release_date: "2026-01-01", end_date: "2030-12-31", rating: "T13", language: "Tiếng Việt" }];
const rooms = [{ id: 1, theater_id: 1, name: "Phòng 01", capacity: 20, room_type: "2D", status: "ACTIVE" }];
const prices = [{ id: 1, room_id: 1, name: "Standard", base_price: "75000" }];
const seats = [{ id: 1, room_id: 1, seat_type_id: 1, seat_name: "A1" }];
const employees = [{ ...user, email: "admin@example.com", phone: "0900000000", role_id: 1, is_active: true }];
const documents = [];
const shows = [];
const rolePermissions = new Map([[1, permissions], [2, permissions.slice(0, 4)], [3, []]]);
let role = "ADMIN";
let rejectSchedule = true;
const writes = [];

await page.route("**/*", async (route) => {
  const request = route.request();
  if (!["fetch", "xhr"].includes(request.resourceType())) return route.continue();
  const url = new URL(request.url());
  const path = url.pathname.replace(/^\/api/, "").replace(/\/$/, "");
  const method = request.method();
  const body = method !== "GET" && request.postData() ? request.postDataJSON() : null;
  if (body) writes.push({ path, method, body });
  const respond = (data, status = 200) => route.fulfill({ status, json: data });
  if (path === "/admin/session") {
    if (role === "USER") return respond({ detail: "Không đủ quyền" }, 403);
    return respond({ user: { ...user, role }, permissions: role === "MANAGER" ? permissions.slice(0, 4) : permissions });
  }
  if (path === "/admin/catalog") return respond({ films, rooms, genres: [{ id: 1, name: "Hành động" }], formats: [{ id: 1, name: "2D", code: "2D" }], theaters: [{ id: 1, name: "CGV Kiểm thử" }] });
  if (path === "/access-control/roles") return respond(roles);
  if (path === "/access-control/permissions") return respond(permissions.map((code, index) => ({ id: index + 1, code, name: code })));
  const permissionMatch = path.match(/^\/access-control\/roles\/(\d+)\/permissions$/);
  if (permissionMatch) {
    const id = Number(permissionMatch[1]);
    if (method === "PUT") { rolePermissions.set(id, body.permission_ids.map((i) => permissions[i - 1])); return respond(body); }
    return respond((rolePermissions.get(id) || []).map((code) => ({ id: permissions.indexOf(code) + 1, code, name: code })));
  }
  const assignment = path.match(/^\/access-control\/users\/(\d+)\/role$/);
  if (assignment) {
    const employee = employees.find((item) => item.id === Number(assignment[1]));
    Object.assign(employee, { role_id: body.role_id, role: roles.find((item) => item.id === body.role_id)?.code });
    return respond(employee);
  }
  const status = path.match(/^\/admin\/employees\/(\d+)\/status$/);
  if (status) { const employee = employees.find((item) => item.id === Number(status[1])); Object.assign(employee, body); return respond(employee); }
  if (path === "/admin/rooms/1/seats") {
    if (method === "GET") return respond({ room: rooms[0], seats, seat_types: prices });
    const seat = { ...body, id: seats.length + 1, room_id: 1 }; seats.push(seat); return respond(seat, 201);
  }
  const docMatch = path.match(/^\/admin\/documents\/(\d+)(\/approval)?$/);
  if (docMatch) {
    const doc = documents.find((item) => item.id === Number(docMatch[1]));
    if (docMatch[2]) { assert.equal(body.version, doc.version); assert.equal(body.expected_updated_at, doc.updated_at); doc.approved = body.approved; return respond(doc); }
    if (method === "DELETE") { documents.splice(documents.indexOf(doc), 1); return respond({ message: "Đã xóa" }); }
    return respond(doc);
  }
  if (path === "/admin/reports") return respond({ revenue: "150000", booking_count: 2, ticket_count: 2, occupied_seats: 2, seat_slots: 20, occupancy: 10,
    sentiments: { positive: 3, neutral: 1, negative: 1, total: 6, pending: 1, coverage: 83.33 }, by_film: [{ film_id: 1, title: films[0].title, revenue: "150000", bookings: 2, tickets: 2 }],
    filters: Object.fromEntries(url.searchParams), as_of: new Date().toISOString() });
  const entities = { films, rooms, prices, employees, documents, showtimes: shows };
  const match = path.match(/^\/admin\/(films|rooms|prices|employees|documents|showtimes)(?:\/(\d+))?$/);
  if (match) {
    const items = entities[match[1]];
    if (method === "GET") {
      const q = (url.searchParams.get("q") || "").toLowerCase();
      const filtered = items.filter((item) => !q || (item.title || item.name || item.username || "").toLowerCase().includes(q));
      return respond({ items: filtered, total: filtered.length });
    }
    if (match[1] === "showtimes" && rejectSchedule) { rejectSchedule = false; return respond({ detail: "Lịch chiếu bị trùng trong phòng. Vui lòng chọn lại thời gian." }, 409); }
    if (method === "DELETE") { items.splice(items.findIndex((item) => item.id === Number(match[2])), 1); return respond({ message: "Đã xóa" }); }
    const item = { ...body, id: Number(match[2]) || items.length + 1 };
    if (match[1] === "employees") { item.is_active = true; item.role = roles.find((r) => r.id === body.role_id)?.code; }
    if (match[1] === "documents") Object.assign(item, { approved: false, updated_at: new Date().toISOString(), chunks: [{ id: 1, content: body.content, embedding_version: "test" }] });
    if (match[1] === "showtimes") item.status = "ACTIVE";
    if (match[2]) items.splice(items.findIndex((old) => old.id === item.id), 1, item); else items.push(item);
    return respond(item, method === "POST" ? 201 : 200);
  }
  if (path === "/ai/conversations") return respond([]);
  return respond({ detail: `Unexpected test request ${method} ${path}` }, 404);
});

try {
  await page.goto(`${baseURL}/admin`);
  await page.getByRole("heading", { name: "Quản lý phim", exact: true }).waitFor();
  await page.getByRole("button", { name: "Thêm phim", exact: false }).click();
  await page.getByLabel("Tên phim *", { exact: true }).fill("Phim mới kiểm thử");
  await page.getByLabel("Hành động", { exact: true }).check();
  await page.getByLabel("2D", { exact: true }).check();
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await page.getByRole("cell", { name: /Phim mới kiểm thử/ }).waitFor();
  assert.deepEqual(writes.find((write) => write.path === "/admin/films").body.genre_ids, [1]);

  await page.getByRole("link", { name: "Phòng chiếu & ghế", exact: true }).click();
  await page.getByRole("link", { name: "Sơ đồ ghế" }).click();
  await page.getByRole("button", { name: "Thêm ghế", exact: false }).click();
  await page.getByLabel("Vị trí ghế *").fill("A2");
  await page.getByLabel("Loại ghế *", { exact: true }).selectOption("1");
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await page.getByRole("button", { name: "Sửa ghế A2", exact: true }).waitFor();

  await page.getByRole("link", { name: "Lịch chiếu", exact: true }).click();
  await page.getByRole("button", { name: "Thêm suất chiếu", exact: false }).click();
  await page.getByLabel("Phim *", { exact: true }).selectOption("1");
  await page.getByLabel("Phòng chiếu *", { exact: true }).selectOption("1");
  await page.getByLabel("Định dạng *", { exact: true }).selectOption("1");
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await page.getByRole("alert").filter({ hasText: "Lịch chiếu bị trùng" }).waitFor();
  assert.equal(await page.getByLabel("Phim *", { exact: true }).inputValue(), "1");
  await page.getByLabel("Giờ bắt đầu *").fill("15:00");
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await page.getByRole("cell", { name: "15:00 – 20:00", exact: true }).waitFor();

  await page.getByRole("link", { name: "Giá vé", exact: true }).click();
  await page.getByRole("button", { name: "Sửa", exact: true }).click();
  await page.getByLabel("Giá vé (VNĐ) *", { exact: true }).fill("99000");
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await page.getByRole("cell", { name: /99.000/ }).waitFor();

  await page.getByRole("link", { name: "Nhân viên", exact: true }).click();
  await page.getByRole("button", { name: "Thêm nhân viên", exact: false }).click();
  await page.getByLabel("Họ và tên *").fill("Nhân viên kiểm thử");
  await page.getByLabel("Email *", { exact: true }).fill("staff@example.com");
  await page.getByLabel("Tên đăng nhập *").fill("staff.test");
  await page.getByLabel(/Mật khẩu ban đầu/).fill("test-password-123");
  await page.getByLabel("Vai trò *", { exact: true }).selectOption("3");
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  const staff = page.getByRole("row").filter({ hasText: "staff@example.com" });
  await staff.getByRole("button", { name: "Vai trò", exact: true }).click();
  await page.getByRole("dialog").getByLabel("Vai trò", { exact: true }).selectOption("2");
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await staff.getByRole("cell", { name: "Quản lý", exact: true }).waitFor();
  await staff.getByRole("button", { name: "Khóa", exact: true }).click();
  await page.getByRole("button", { name: "Xác nhận", exact: true }).click();
  await staff.getByText("Đã khóa", { exact: true }).waitFor();

  await page.getByRole("link", { name: "Phân quyền", exact: true }).click();
  await page.getByLabel("Vai trò", { exact: true }).selectOption("3");
  await page.getByLabel("reports.view (reports.view)", { exact: true }).check();
  await page.getByRole("button", { name: "Lưu phân quyền" }).click();
  await page.getByRole("status").filter({ hasText: "Đã lưu phân quyền" }).waitFor();

  await page.getByRole("link", { name: "Tài liệu chatbot", exact: true }).click();
  await page.getByRole("button", { name: "Nhập tài liệu", exact: false }).click();
  await page.getByLabel("Mã nguồn tài liệu *").fill("policy-test");
  await page.getByLabel("Tiêu đề *", { exact: true }).fill("Chính sách đặt vé kiểm thử");
  await page.getByLabel("Nội dung tài liệu *").fill("Đặt vé bằng cách chọn phim, suất chiếu và ghế ngồi.");
  await page.getByRole("button", { name: "Lưu & xử lý tài liệu" }).click();
  await page.getByRole("button", { name: "Xem / duyệt" }).click();
  await page.getByRole("button", { name: "Phê duyệt phiên bản này" }).click();
  await page.getByRole("cell", { name: "Đã duyệt", exact: true }).waitFor();
  assert.equal(documents[0].approved, true);

  await page.getByRole("link", { name: "Báo cáo thống kê", exact: true }).click();
  await page.getByText("150.000", { exact: false }).first().waitFor();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Xuất CSV" }).click();
  assert.match((await download).suggestedFilename(), /^bao-cao-.*\.csv$/);
  if (screenshotDir) await page.screenshot({ path: resolve(screenshotDir, "admin-reports-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "Report must fit mobile viewport");
  if (screenshotDir) await page.screenshot({ path: resolve(screenshotDir, "admin-reports-mobile.png"), fullPage: true });
  await page.goto(`${baseURL}/admin/films`);
  await page.getByRole("heading", { name: "Quản lý phim", exact: true }).waitFor();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "Film table scrolls inside its panel on mobile");
  if (screenshotDir) await page.screenshot({ path: resolve(screenshotDir, "admin-films-mobile.png"), fullPage: true });

  role = "MANAGER";
  await page.goto(`${baseURL}/admin`);
  await page.getByRole("heading", { name: "Quản lý phim", exact: true }).waitFor();
  assert.equal(await page.getByRole("link", { name: "Nhân viên", exact: true }).count(), 0);
  await page.goto(`${baseURL}/admin/employees`);
  await page.getByRole("heading", { name: "Không đủ quyền", exact: true }).waitFor();
  role = "USER";
  await page.goto(`${baseURL}/admin`);
  await page.getByRole("heading", { name: "Không thể truy cập", exact: true }).waitFor();
  assert.deepEqual(errors, []);
  console.log("Admin browser workflows passed: films, seats, schedule conflicts, prices, employees, roles, knowledge approval, report CSV, mobile layout and access guards.");
} catch (error) {
  if (screenshotDir) await page.screenshot({ path: resolve(screenshotDir, "admin-failure.png"), fullPage: true });
  throw error;
} finally {
  await browser.close();
}
