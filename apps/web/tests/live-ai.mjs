// Explicit opt-in: uses the actual local backend, Qwen and authorized DEMO data.
// Only holds/releases one DEMO seat. Does not create an order or call Payment.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

if (process.env.CINEMA_LIVE_DEMO_TEST !== '1') throw new Error('Set CINEMA_LIVE_DEMO_TEST=1 to test the authorized local DEMO runtime');
const root = fileURLToPath(new URL('../../../', import.meta.url));
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:5173';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
const access = JSON.parse(await readFile(resolve(root, process.env.CINEMA_DEMO_CREDENTIALS || '.local/runtime/demo-access.json'), 'utf8'));
assert.equal(access.username, process.env.CINEMA_DEMO_USERNAME || 'cinema_demo_admin');
const evidence = resolve(root, '.local/evidence/live-ui');
await mkdir(evidence, { recursive: true });
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
const page = await browser.newPage({ viewport: { width: 1365, height: 1000 } });
const errors = [], turns = [];
let held = null, finalReport = null;
page.on('pageerror', error => errors.push(error.message));
async function ask(message) {
  await page.getByLabel('Câu hỏi cho trợ lý').fill(message);
  const pending = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/ai/chat') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Gửi', exact: true }).click();
  const response = await pending;
  assert.equal(response.status(), 200);
  const body = await response.json();
  turns.push({ message, ...body });
  await page.getByRole('button', { name: 'Gửi', exact: true }).waitFor();
  return body;
}
try {
  await page.goto(base+'/login');
  await page.getByLabel('Tên đăng nhập').fill(access.username);
  await page.getByLabel('Mật khẩu', { exact: true }).fill(access.password);
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.waitForFunction(() => Boolean(JSON.parse(localStorage.getItem('userInfo') || 'null')?.access_token));
  await page.goto(base+'/movie');
  await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
  const first = await ask('Tối mai tôi muốn xem phim hài, hai người, tổng tiền vé dưới 250k, sau 18h.');
  assert.equal(first.status, 'ok');
  assert.equal(first.mode, 'model_planned');
  assert.ok(first.cards.length > 0);
  const card = first.cards[0];
  assert.ok(card.film_title.startsWith('DEMO - '));
  assert.equal(card.party_size, 2);
  assert.equal(Number(card.minimum_total), 160000);
  assert.equal(card.available_seats, 12);
  assert.notEqual(first.context.film_id, 2, 'The title Mai must not capture tomorrow');
  await page.getByRole('log').getByRole('heading', { name: card.film_title, exact: true }).waitFor();
  await page.screenshot({ path: resolve(evidence, 'chat-cards-desktop.png'), fullPage: true });
  const second = await ask('Suất thứ 1 còn ghế nào?');
  assert.equal(second.status, 'ok');
  assert.equal(second.tool, 'get_seat_availability');
  assert.equal(second.context.showtime_id, card.showtime_id);
  await page.getByRole('log').getByRole('link', { name: 'Chọn ghế', exact: true }).first().click();
  await page.getByRole('heading', { name: 'Chọn ghế', exact: true }).waitFor();
  const seats = await page.request.get(base+`/api/seats/showtime/${card.showtime_id}`);
  assert.equal(seats.status(), 200);
  const a1 = (await seats.json()).find(seat => seat.seat_name === 'A1');
  assert.equal(a1.status, 'AVAILABLE');
  held = { showtime_id: card.showtime_id, seat_ids: [a1.seat_id] };
  const hold = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/seats/hold'));
  await page.getByRole('button', { name: /^Ghế A1,/ }).click();
  assert.equal((await hold).status(), 200);
  const selected = page.getByRole('button', { name: /^Ghế A1,/ });
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(button => button.getAttribute('aria-label')?.startsWith('Ghế A1,') && button.getAttribute('aria-pressed') === 'true'));
  await page.screenshot({ path: resolve(evidence, 'seat-selected.png'), fullPage: true });
  const release = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/seats/release'));
  await selected.click();
  assert.equal((await release).status(), 200);
  held = null;
  await page.goto(base+'/movie');
  await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
  const clarify = await ask('Ngày mai hai người muốn xem phim hài dưới 250k.');
  assert.equal(clarify.status, 'needs_clarification');
  assert.deepEqual(clarify.missing_fields, ['budget_scope']);
  const completed = await ask('Tổng cả nhóm');
  assert.equal(completed.status, 'ok');
  assert.equal(completed.cards[0].party_size, 2);
  const none = await ask('Tổng ngân sách dưới 100k.');
  assert.equal(none.status, 'no_results');
  assert.deepEqual(none.cards, []);
  const unsupported = await ask('Giữ ghế và thanh toán hộ tôi nhé.');
  assert.equal(unsupported.status, 'out_of_scope');
  await page.reload();
  await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
  await page.getByRole('button', { name: 'Lịch sử', exact: true }).click();
  await page.getByRole('button', { name: /^Tối mai tôi muốn xem phim hài, hai người/ }).first().click();
  await page.getByRole('log').getByRole('heading', { name: card.film_title, exact: true }).waitFor();
  await page.setViewportSize({ width: 390, height: 900 });
  await page.screenshot({ path: resolve(evidence, 'history-mobile.png'), fullPage: true });
  assert.deepEqual(errors, []);
  finalReport = { stage: 'live local application with actual owner APIs, PostgreSQL, Redis and Ollama',
    checked: ['normal UI login', 'live movie/date/budget filtering', 'short title disambiguation', 'ordinal follow-up', 'actual DEMO seat hold and release', 'budget clarification', 'no-result budget', 'no automatic payment', 'history after reload'],
    demoOnly: true, createdOrders: 0, paymentCalls: 0, browserErrors: errors, turns };
  await writeFile(resolve(evidence, 'report.json'), JSON.stringify(finalReport, null, 2));
  console.log(JSON.stringify({ passed: finalReport.checked, models: [...new Set(turns.map(turn => turn.mode))], browserErrors: errors }));
} catch (error) {
  await page.screenshot({ path: resolve(evidence, 'failure.png'), fullPage: true });
  console.error('Live AI check failed:', error.message);
  throw error;
} finally {
  if (held) {
    await page.evaluate(async payload => {
      const user = JSON.parse(localStorage.getItem('userInfo') || 'null');
      if (user?.access_token) await fetch('/api/seats/release', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer '+user.access_token }, body: JSON.stringify(payload) });
    }, held).catch(() => {});
  }
  await browser.close();
}
