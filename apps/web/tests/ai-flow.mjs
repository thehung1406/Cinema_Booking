// Browser integration with isolated API fixtures. No backend/payment writes.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
const page = await browser.newPage({ viewport: { width: 375, height: 900 } });
const errors = [], decisions = [], publications = [];
page.on('pageerror', error => errors.push(error.message));
const user = { id: 1, role: 'ADMIN', full_name: 'AI UI test', access_token: 'isolated-test-token', permissions: ['reviews.moderate', 'knowledge.manage'] };
await page.addInitScript(value => localStorage.setItem('userInfo', JSON.stringify(value)), user);
const stamp = '2026-11-03T07:00:00Z';
const savedChat = { id: '33333333-3333-4333-8333-333333333333', title: 'Hội thoại đã lưu', updated_at: stamp };
let savedChatDeleted = false;
const doc = { id: 8, source_id: 'ui-book', title: 'Sách kiểm thử riêng', version: '1', source_url: 'https://example.org/fixture.pdf',
  effective_at: stamp, updated_at: stamp, approved: false,
  provenance: { source_type: 'pdf', scope: 'film_education', author: 'UI fixture author', license: 'test fixture only', checksum: 'a'.repeat(64), language: 'vi' },
  chunks: [{ id: 9, content: 'Nội dung kiểm thử PDF.', provenance: { page_start: 7 } }] };
const draft = { id: '22222222-2222-4222-8222-222222222222', title: doc.title, version: '2', published_at: null,
  document: { blocks: [{ text: 'Nội dung phiên bản PDF mới.' }] } };
await page.route('**/*', async route => {
  const req = route.request();
  if (!['xhr', 'fetch'].includes(req.resourceType())) return route.continue();
  const path = new URL(req.url()).pathname.replace(/^\/api/, '').replace(/\/$/, '');
  let body = [], status = 200;
  if (path === '/ai/chat') body = { conversation_id: '11111111-1111-4111-8111-111111111111', answer: 'Suất phù hợp với nhóm bạn. [doc:9] Xem thêm hướng dẫn. [doc:10]', status: 'ok', mode: 'model_planned', context: {}, as_of: stamp, has_more: true,
    cards: [{ kind: 'showtime', showtime_id: 11, film_title: 'Phim hài kiểm thử', theater_name: 'Rạp kiểm thử', show_date: '2030-12-01', start_time: '19:30:00', min_ticket_price: '90000', minimum_total: '180000', party_size: 2, available_seats: 12, url: '/seat-selection/11' }],
    links: [{ url: '/seat-selection/11', title: 'Chọn ghế' }],
    sources: [9, 10].map(id => ({ id: 'doc:'+id, kind: 'document', source_id: doc.source_id, title: doc.title, version: '1', text: doc.chunks[0].content, url: doc.source_url+'#page=7', provenance: { page_start: 7 } })) };
  else if (path === '/ai/conversations') body = savedChatDeleted ? [] : [savedChat];
  else if (path === '/ai/conversations/'+savedChat.id && req.method() === 'DELETE') {
    savedChatDeleted = true;
    body = {};
  }
  else if (path === '/ai/conversations/'+savedChat.id) {
    const older = new URL(req.url()).searchParams.has('before_id');
    body = { ...savedChat, context: {}, next_before_id: older ? null : 2, messages: [
      { id: older ? 1 : 2, role: 'assistant', content: older ? 'Tin nhắn đầu tiên.' : 'Tin nhắn đã lưu.', metadata: {} },
    ] };
  }
  else if (path === '/reviews/sentiment/pending') body = { total: decisions.length >= 2 ? 0 : 1, items: decisions.length >= 2 ? [] : [{ review_id: 21, film_id: 1, content: 'Review kiểm thử giao diện.', content_version: 2, analysis_generation: 3, updated_at: stamp, predicted_label: 'negative', label: null, scores: { positive: .2, neutral: .3, negative: .5 }, model_version: 'ui-fixture-model' }] };
  else if (path === '/reviews/21/sentiment-decision') { decisions.push(req.postDataJSON()); status = decisions.length === 1 ? 503 : 200; body = status === 503 ? { detail: 'Lỗi tạm thời kiểm thử' } : { saved: true }; }
  else if (path === '/admin/session') body = { user, permissions: user.permissions };
  else if (path === '/admin/documents') body = { items: [doc], total: 1 };
  else if (path === '/admin/documents/8') body = doc;
  else if (path === '/admin/documents/8/revisions') body = [draft];
  else if (path === `/admin/documents/8/revisions/${draft.id}`) body = draft;
  else if (path === `/admin/documents/8/revisions/${draft.id}/publication`) {
    publications.push(req.postDataJSON()); body = { ...doc, version: '2' };
  }
  else if (path === '/admin/cinema-operations') body = { items: [] };
  else if (path === '/admin/knowledge/search') body = { strategy: 'bm25', latency_ms: 12, sources: [{ id: 'doc:9', title: doc.title, version: '1', url: doc.source_url+'#page=7', score: 1.25, text: doc.chunks[0].content, provenance: { page_start: 7 } }] };
  await route.fulfill({ status, json: body });
});
try {
  const base = process.env.UI_BASE_URL || 'http://127.0.0.1:5173';
  await page.goto(base+'/about');
  await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
  const assistant = page.getByRole('dialog', { name: 'Trợ lý Cinema' });
  assert.ok((await assistant.boundingBox()).width >= 375);
  assert.equal(await page.getByLabel('Phim cho trợ lý').count(), 0);
  await page.getByRole('button', { name: 'Bộ lọc', exact: true }).click();
  await page.getByLabel('Phim cho trợ lý').waitFor();
  await page.getByRole('button', { name: 'Bộ lọc', exact: true }).click();
  await page.getByRole('button', { name: 'Cách đặt vé', exact: true }).click();
  assert.equal(await page.getByLabel('Câu hỏi cho trợ lý').inputValue(), 'Tôi đặt vé trên website như thế nào?');
  await page.getByLabel('Câu hỏi cho trợ lý').fill('Hai người muốn xem phim hài tối mai.');
  await page.getByRole('button', { name: 'Gửi', exact: true }).click();
  await page.getByText('Phim hài kiểm thử', { exact: true }).waitFor();
  assert.equal(await page.getByRole('link', { name: 'Chọn ghế', exact: true }).getAttribute('href'), '/seat-selection/11');
  assert.ok((await page.getByRole('log').innerText()).includes('180.000'));
  assert.equal(await page.getByRole('button', { name: 'Xem nguồn 1' }).count(), 2);
  await page.getByRole('button', { name: 'Xem nguồn 1' }).first().click();
  await page.getByText('Nguồn tham chiếu (1)', { exact: true }).waitFor();
  assert.equal(await page.getByRole('link', { name: 'Mở nguồn · trang PDF 7' }).getAttribute('href'), doc.source_url+'#page=7');
  await page.getByRole('link', { name: 'Mở nguồn · trang PDF 7' }).waitFor();
  if (process.env.UI_SCREENSHOT_DIR) {
    await mkdir(process.env.UI_SCREENSHOT_DIR, { recursive: true });
    await page.screenshot({ path: process.env.UI_SCREENSHOT_DIR+'/ai-cards-375.png', fullPage: true });
  }
  await page.keyboard.press('Escape');
  await assistant.waitFor({ state: 'detached' });
  assert.equal(await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).evaluate(el => el === document.activeElement), true);
  await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
  await page.getByRole('button', { name: 'Lịch sử', exact: true }).click();
  const savedButton = page.getByRole('button', { name: /^Hội thoại đã lưu/ });
  await savedButton.click();
  await page.getByText('Tin nhắn đã lưu.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Tải tin nhắn cũ hơn', exact: true }).click();
  await page.getByText('Tin nhắn đầu tiên.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Lịch sử', exact: true }).click();
  await page.getByRole('button', { name: 'Xóa hội thoại', exact: true }).click();
  await page.getByText('Tin nhắn đã lưu.', { exact: true }).waitFor({ state: 'detached' });
  assert.equal(await savedButton.count(), 0);
  assert.equal(await page.locator(':focus').getAttribute('id'), 'ai-conversation-history');
  await page.goto(base+'/review-moderation');
  await page.getByRole('tab', { name: 'Nhãn cảm xúc' }).click();
  await page.getByRole('combobox', { name: /Nhãn xác nhận/ }).selectOption('positive');
  await page.getByLabel('Lý do xác nhận hoặc sửa nhãn').fill('Lý do kiểm thử, không phải đánh giá thật.');
  await page.getByRole('button', { name: 'Lưu nhãn xác nhận', exact: true }).click();
  await page.getByText('Lỗi tạm thời kiểm thử', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Lưu nhãn xác nhận', exact: true }).click();
  await page.getByText('Không có đánh giá ở trạng thái này.', { exact: true }).waitFor();
  assert.equal(decisions.length, 2);
  assert.deepEqual(decisions[0], decisions[1], 'Network retry must reuse the same idempotent payload');
  assert.equal(decisions[0].content_version, 2);
  assert.equal(decisions[0].analysis_generation, 3);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base+'/admin/documents');
  await page.getByLabel('Câu hỏi kiểm tra').fill('Khái niệm quay phim là gì?');
  await page.getByRole('button', { name: 'Xem nguồn tìm được' }).click();
  await page.getByText('Nội dung kiểm thử PDF.', { exact: true }).waitFor();
  assert.ok((await page.locator('body').innerText()).includes('Trang PDF 7'));
  await page.getByRole('button', { name: 'Xem / duyệt' }).click();
  await page.getByText('Phiên bản và lịch sử công bố', { exact: true }).click();
  await page.getByRole('button', { name: '2 · Bản nháp' }).click();
  await page.getByText('Nội dung phiên bản PDF mới.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Duyệt và công bố phiên bản này' }).click();
  await page.getByText('Đang phục vụ phiên bản 2.', { exact: true }).waitFor();
  assert.deepEqual(publications, [{ expected_updated_at: stamp }]);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ passed: ['showtime cards on mobile', 'grouped PDF citation', 'saved chat pagination and deletion', 'sentiment CAS and idempotent retry',
    'KB retrieval trace', 'KB revision publication'], browserErrors: errors, data: 'isolated fixtures only' }));
} catch (error) {
  if (process.env.UI_SCREENSHOT_DIR) await page.screenshot({ path: process.env.UI_SCREENSHOT_DIR+'/ai-flow-failure.png', fullPage: true });
  console.error((await page.locator('body').innerText()).slice(-4000));
  throw error;
} finally { await browser.close(); }
