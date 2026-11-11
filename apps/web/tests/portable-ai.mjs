// Real portable DEMO runtime. Reads chat/seat data; never checks out or pays.
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

if (process.env.CINEMA_PORTABLE_DEMO_TEST !== '1' || !process.env.CINEMA_DEMO_CREDENTIALS) {
  throw new Error('Explicit CINEMA_PORTABLE_DEMO_TEST=1 and local CINEMA_DEMO_CREDENTIALS file required');
}
const root = fileURLToPath(new URL('../../../', import.meta.url));
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:5173';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
const access = JSON.parse(await readFile(resolve(root, process.env.CINEMA_DEMO_CREDENTIALS), 'utf8'));
const evidence = resolve(root, '.local/evidence/portable-ui');
await mkdir(evidence, { recursive: true });
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
const page = await browser.newPage({ viewport: { width: 1365, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto(base + '/login');
  await page.getByLabel('Tên đăng nhập').fill(access.username);
  await page.getByLabel('Mật khẩu', { exact: true }).fill(access.password);
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.waitForFunction(() => Boolean(JSON.parse(localStorage.getItem('userInfo') || 'null')?.access_token));
  await page.goto(base + '/movie');
  await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
  await page.getByLabel('Câu hỏi cho trợ lý').fill('Tối mai tôi muốn xem phim hài, hai người, tổng dưới 200k.');
  const pending = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/ai/chat') && response.request().method() === 'POST', { timeout: 60000 });
  await page.getByRole('button', { name: 'Gửi', exact: true }).click();
  const response = await pending;
  assert.equal(response.status(), 200);
  const body = await response.json();
  assert.equal(body.status, 'ok');
  assert.equal(body.mode, 'model_planned');
  const card = body.cards[0];
  assert.ok(card.film_title.startsWith('DEMO - '));
  assert.equal(card.party_size, 2);
  assert.equal(Number(card.minimum_total), 160000);
  await page.getByRole('log').getByRole('heading', { name: card.film_title, exact: true }).waitFor();
  await page.screenshot({ path: resolve(evidence, 'chat.png'), fullPage: true });
  await page.getByRole('log').getByRole('link', { name: 'Chọn ghế', exact: true }).first().click();
  await page.getByRole('heading', { name: 'Chọn ghế', exact: true }).waitFor();
  const seat = page.getByRole('button', { name: /^Ghế A1,/ });
  await seat.waitFor();
  assert.equal(await seat.getAttribute('aria-pressed'), 'false');
  await page.screenshot({ path: resolve(evidence, 'seats.png'), fullPage: true });
  assert.deepEqual(errors, []);
  await writeFile(resolve(evidence, 'report.json'), JSON.stringify({ stage: 'real-portable-runtime-ui-smoke', chat_mode: body.mode,
    showtime_id: card.showtime_id, minimum_total: card.minimum_total, party_size: card.party_size, seat_page_opened: true,
    holds_created: false, orders_created: false, payment_called: false, browser_errors: errors }, null, 2));
  console.log(JSON.stringify({ chat_mode: body.mode, seat_page_opened: true, browser_errors: errors.length }));
} finally {
  await browser.close();
}
