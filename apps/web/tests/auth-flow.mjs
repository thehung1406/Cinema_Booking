// Isolated fixtures: no account is created on a real backend.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:5173';
const shots = process.env.UI_SCREENSHOT_DIR;
if (shots) await mkdir(shots, { recursive: true });
const page = await browser.newPage();
const errors = [], registrations = [], logins = [];
let reject = true;
page.on('pageerror', e => errors.push(e.message));
await page.route('**/*', async route => {
  const request = route.request();
  if (!['fetch', 'xhr'].includes(request.resourceType())) return route.continue();
  const path = new URL(request.url()).pathname.replace(/^\/api/, '');
  if (path === '/auth/register') {
    registrations.push(request.postDataJSON());
    return route.fulfill({ status: reject ? 503 : 201, json: reject ? { detail: 'Chưa kết nối được. Vui lòng thử lại.' } : { id: 7, username: 'auth-test', role: 'CUSTOMER' } });
  }
  if (path === '/auth/login') { logins.push(request.postData()); return route.fulfill({ json: { access_token: 'fixture-only' } }); }
  if (path === '/auth/me') return route.fulfill({ json: { id: 7, username: 'auth-test', role: 'CUSTOMER' } });
  return route.fulfill({ json: [] });
});
async function signup() {
  await page.goto(base + '/login');
  await page.getByRole('button', { name: 'Đăng ký tài khoản', exact: true }).click();
  await page.getByRole('heading', { name: 'Tạo tài khoản', exact: true }).waitFor();
}
async function fill(password) {
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill('auth-test');
  await page.getByLabel('Họ và tên', { exact: true }).fill('Người kiểm thử');
  await page.getByLabel('Email', { exact: true }).fill('auth-test@gmail.com');
  await page.getByLabel('Mật khẩu', { exact: true }).fill(password);
  await page.getByLabel('Xác nhận mật khẩu', { exact: true }).fill(password);
}
try {
  await signup();
  assert.equal(await page.getByLabel('Mật khẩu', { exact: true }).getAttribute('minlength'), '8');
  await fill('1234567');
  await page.getByRole('button', { name: 'Tạo tài khoản', exact: true }).click();
  assert.equal(registrations.length, 0, 'Native validation prevents a short password request');
  await page.locator('form').evaluate(form => { form.noValidate = true; });
  await page.getByRole('button', { name: 'Tạo tài khoản', exact: true }).click();
  await page.getByText('Mật khẩu phải có ít nhất 8 ký tự', { exact: true }).first().waitFor();
  assert.equal(registrations.length, 0, 'Submit validation also enforces eight characters');
  await fill('😀😀😀😀');
  await page.getByRole('button', { name: 'Tạo tài khoản', exact: true }).click();
  assert.equal(registrations.length, 0, 'Unicode characters are counted correctly');
  await fill('ắ'.repeat(25));
  await page.getByRole('button', { name: 'Tạo tài khoản', exact: true }).click();
  await page.getByText('Mật khẩu không được vượt quá 72 byte UTF-8', { exact: true }).first().waitFor();
  assert.equal(registrations.length, 0);
  await fill('12345678');
  await page.getByRole('button', { name: 'Tạo tài khoản', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'Chưa kết nối được' }).waitFor();
  assert.equal(await page.getByLabel('Mật khẩu', { exact: true }).inputValue(), '12345678');
  reject = false;
  await page.getByRole('button', { name: 'Tạo tài khoản', exact: true }).click();
  await page.waitForURL(base + '/');
  assert.equal(registrations.length, 2);
  assert.equal(logins.length, 1, 'Registration still automatically logs in');
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await signup();
    assert.equal(await page.locator('h1').evaluate(el => el === document.activeElement), true, 'Mode switch focuses its heading');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Signup fits its viewport');
    if (shots) {
      await page.evaluate(async () => { await document.fonts.ready; await Promise.all(document.getAnimations().map(a => a.finished.catch(() => {}))); });
      await page.screenshot({ path: `${shots}/signup-motion-${width}.png`, fullPage: true });
    }
    await page.getByLabel('Tên đăng nhập', { exact: true }).fill('preserve-me');
    await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
    assert.equal(await page.getByLabel('Tên đăng nhập', { exact: true }).inputValue(), 'preserve-me');
    assert.equal(await page.getByLabel('Mật khẩu', { exact: true }).getAttribute('minlength'), null, 'Existing login credentials keep their current rules');
    assert.equal(await page.locator('.auth-form-panel').evaluate(el => getComputedStyle(el).animationName), 'auth-panel-enter');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    if (shots) {
      await page.evaluate(async () => { await document.fonts.ready; await Promise.all(document.getAnimations().map(a => a.finished.catch(() => {}))); });
      await page.screenshot({ path: `${shots}/auth-motion-${width}.png`, fullPage: true });
    }
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await signup();
  assert.equal(await page.locator('.auth-form-panel').evaluate(el => getComputedStyle(el).animationName), 'none');
  assert.equal(await page.locator('h1').isVisible(), true);
  assert.deepEqual(errors, []);
  console.log('Auth passed: 7/8 characters, Unicode/72 bytes, failure/retry, auto login, mode focus/data preservation, five widths and reduced motion.');
} finally { await browser.close(); }
