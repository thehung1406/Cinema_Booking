// Browser regression using isolated API fixtures; never writes to the live backend.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.setDefaultTimeout(10000);
const user = { id: 9, role: 'STAFF', username: 'review-staff', access_token: 'isolated-token', permissions: ['reviews.moderate'] };
await page.addInitScript(value => localStorage.setItem('userInfo', JSON.stringify(value)), user);
const errors = [], writes = [];
page.on('pageerror', error => errors.push(error.message));
let failList = false, failDelete = false, reviewOnly = true, mine = null;
const rows = Array.from({ length: 25 }, (_, index) => ({ id: index + 1, film_id: index % 2 + 1,
  author: `Khán giả ${index + 1}`, content: `Nhận xét phim số ${index + 1}`, content_version: 1,
  updated_at: '2026-11-20T05:00:00Z', moderation_status: index === 1 ? 'rejected' : 'approved',
  analysis_status: index === 2 ? 'failed' : index === 3 ? 'pending' : 'succeeded',
  sentiment: index === 2 || index === 3 ? null : 'positive', scores: { positive: .7, neutral: .2, negative: .1 }, model_version: 'fixture-model' }));
await page.route('**/api/**', async route => {
  const request = route.request(), url = new URL(request.url()), path = url.pathname.replace(/^\/api/, '').replace(/\/$/, '');
  const respond = (body, status = 200) => route.fulfill({ status, json: body });
  if (path === '/admin/session') return respond({ user, permissions: reviewOnly ? user.permissions : ['films.manage'] });
  if (path === '/reviews') {
    if (failList) { failList = false; return respond({ detail: 'Lỗi tải nhận xét kiểm thử' }, 503); }
    const params = url.searchParams;
    const filtered = rows.filter(row => (!params.get('q') || row.content.includes(params.get('q')))
      && ['film_id', 'sentiment', 'analysis_status', 'moderation_status'].every(key => !params.get(key) || String(row[key]) === params.get(key)));
    const offset = Number(params.get('offset') || 0), limit = Number(params.get('limit') || 20);
    return respond({ items: filtered.slice(offset, offset + limit), total: filtered.length });
  }
  if (/^\/reviews\/\d+$/.test(path) && request.method() === 'DELETE') {
    if (failDelete) { failDelete = false; return respond({ detail: 'Chưa xóa được nhận xét kiểm thử' }, 503); }
    const id = Number(path.split('/').at(-1)); writes.push(id);
    rows.splice(rows.findIndex(row => row.id === id), 1);
    return route.fulfill({ status: 204, body: '' });
  }
  if (path === '/films/1') return respond({ id: 1, title: 'Phim kiểm thử', duration: '100 phút', formats: [] });
  if (path === '/films/1/sentiment-summary') return respond({ total: 0, positive: 0, neutral: 0, negative: 0,
    pending: 1, needs_review: 0, window_days: 30, min_reviews: 10, eligible: false });
  if (path === '/films/1/reviews/mine') return respond(mine);
  if (path === '/films/1/reviews') {
    if (request.method() === 'POST') {
      mine = { ...rows[0], id: 100, content: request.postDataJSON().content, analysis_status: 'pending', sentiment: null,
        moderation_status: 'approved', verified_purchase: true };
      return respond(mine, 201);
    }
    return respond(mine ? [mine] : []);
  }
  if (path === '/ai/conversations') return respond([]);
  return respond({ detail: `Unexpected fixture request: ${path}` }, 404);
});

try {
  const base = process.env.UI_BASE_URL || 'http://127.0.0.1:5174';
  await page.goto(base + '/review-moderation');
  await page.getByRole('heading', { name: 'Nhận xét người dùng', exact: true }).waitFor();
  assert.equal(new URL(page.url()).pathname, '/admin/reviews');
  assert.equal(await page.locator('.admin-sidebar nav a').count(), 1);
  assert.equal(await page.getByRole('button', { name: /Duyệt|Xác nhận nhãn/ }).count(), 0);
  await page.getByText('1–20 / 25 bản ghi', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Sau', exact: true }).click();
  await page.getByText('21–25 / 25 bản ghi', { exact: true }).waitFor();
  await page.getByLabel('Nội dung', { exact: true }).fill('số 25');
  await page.getByText('1–1 / 1 bản ghi', { exact: true }).waitFor();
  await page.getByLabel('Nội dung', { exact: true }).fill('');
  for (const [label, value, count, author] of [['Công khai', 'rejected', '1–1 / 1 bản ghi', 'Khán giả 2'],
    ['Phân tích', 'failed', '1–1 / 1 bản ghi', 'Khán giả 3'], ['Cảm xúc', 'positive', '1–20 / 23 bản ghi', 'Khán giả 1']]) {
    await page.getByLabel(label, { exact: true }).selectOption(value);
    await page.getByText(count, { exact: true }).waitFor();
    await page.getByRole('cell').filter({ hasText: author }).first().waitFor();
    await page.getByLabel(label, { exact: true }).selectOption('');
    await page.getByText('1–20 / 25 bản ghi', { exact: true }).waitFor();
  }
  await page.getByLabel('Mã phim', { exact: true }).fill('2');
  await page.getByText('1–12 / 12 bản ghi', { exact: true }).waitFor();
  await page.getByLabel('Mã phim', { exact: true }).fill('');
  await page.getByText('1–20 / 25 bản ghi', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Xóa', exact: true }).first().click();
  await page.getByRole('button', { name: 'Hủy', exact: true }).click();
  assert.deepEqual(writes, []);
  failDelete = true;
  await page.getByRole('button', { name: 'Xóa', exact: true }).first().click();
  await page.getByRole('button', { name: 'Xác nhận', exact: true }).click();
  await page.getByText('Chưa xóa được nhận xét kiểm thử', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Xác nhận', exact: true }).click();
  await page.getByText('Đã xóa nhận xét.', { exact: true }).waitFor();
  assert.deepEqual(writes, [1]);
  failList = true;
  await page.reload();
  await page.getByText('Lỗi tải nhận xét kiểm thử', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Thử lại', exact: true }).click();
  await page.getByText('1–20 / 24 bản ghi', { exact: true }).waitFor();
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
  }
  if (process.env.UI_SCREENSHOT_DIR) {
    await mkdir(process.env.UI_SCREENSHOT_DIR, { recursive: true });
    await page.screenshot({ path: process.env.UI_SCREENSHOT_DIR + '/reviews-dashboard.png', fullPage: true });
  }
  reviewOnly = false;
  await page.reload();
  await page.getByRole('heading', { name: 'Không đủ quyền', exact: true }).waitFor();
  await page.goto(base + '/movie/1');
  await page.getByLabel('Viết cảm nhận về phim').fill('Nhận xét được đăng ngay');
  assert.equal(await page.getByRole('link', { name: 'Duyệt đánh giá phim', exact: false }).count(), 0);
  await page.getByRole('button', { name: 'Gửi đánh giá', exact: true }).click();
  await page.getByText('Đánh giá đã được đăng.', { exact: true }).waitFor();
  assert.equal(await page.getByText('Nhận xét được đăng ngay', { exact: true }).count(), 2);
  assert.equal((await page.locator('body').innerText()).includes('chờ duyệt'), false);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ passed: ['redirect and review-only permission', 'filters and pagination', 'delete cancellation and retry',
    'load failure and retry', 'mobile layout', 'immediate public review with pending analysis'], browserErrors: errors }));
} finally {
  await browser.close();
}
