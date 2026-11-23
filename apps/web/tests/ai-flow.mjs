// Browser integration with isolated API fixtures. No backend/payment writes.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
const page = await browser.newPage({ viewport: { width: 375, height: 900 } });
const errors = [], publications = [];
page.on('pageerror', error => errors.push(error.message));
const user = { id: 1, role: 'ADMIN', full_name: 'AI UI test', access_token: 'isolated-test-token', permissions: ['reviews.moderate', 'knowledge.manage'] };
await page.addInitScript(value => localStorage.setItem('userInfo', JSON.stringify(value)), user);
const stamp = '2026-11-03T07:00:00Z';
const chatId = '11111111-1111-4111-8111-111111111111';
const savedChat = { id: '33333333-3333-4333-8333-333333333333', title: 'Hội thoại đã lưu', updated_at: stamp };
let savedChatDeleted = false;
let chatContext = { film_id: 1, theater_id: 1, show_date: '2030-12-01' };
let chatFailure = null;
const resetQuestion = 'Lịch chiếu sau khi xóa bộ lọc?';
const resetRequests = [];
const rawChatError = 'Chi tiết kỹ thuật kiểm thử';
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
  if (path === '/ai/chat' && req.postDataJSON().message === resetQuestion) {
    const payload = req.postDataJSON();
    resetRequests.push(payload);
    if (chatFailure === 'network') return route.abort('failed');
    if (chatFailure) {
      status = chatFailure;
      body = { detail: rawChatError };
    } else {
      chatContext = { ...(payload.reset_filters ? {} : chatContext), ...payload.context };
      body = { conversation_id: chatId, answer: 'Đã tra lịch với bộ lọc hiện tại.', context: chatContext,
        status: 'ok', as_of: stamp, showtime_options: true };
    }
  }
  else if (path === '/ai/chat') body = { conversation_id: chatId, answer: 'Suất phù hợp với nhóm bạn. [doc:9] Xem thêm hướng dẫn. [doc:10]', status: 'ok', mode: 'model_planned', context: chatContext, as_of: stamp, has_more: true,
    cards: [{ kind: 'showtime', showtime_id: 11, film_title: 'Phim hài kiểm thử', theater_name: 'Rạp kiểm thử', show_date: '2030-12-01', start_time: '19:30:00', min_ticket_price: '90000', minimum_total: '180000', party_size: 2, available_seats: 12, url: '/seat-selection/11' }],
    links: [{ url: '/seat-selection/11', title: 'Chọn ghế' }],
    sources: [9, 10].map(id => ({ id: 'doc:'+id, kind: 'document', source_id: doc.source_id, title: doc.title, version: '1', text: doc.chunks[0].content, url: doc.source_url+'#page=7', provenance: { page_start: 7 } })) };
  else if (path === '/ai/conversations') body = savedChatDeleted ? [] : [savedChat];
  else if (path === '/ai/conversations/'+chatId) body = { id: chatId, context: chatContext, messages: [
    { id: 3, role: 'assistant', content: 'Lịch chiếu đã lưu.', metadata: {} },
  ] };
  else if (path === '/ai/conversations/'+savedChat.id && req.method() === 'DELETE') {
    savedChatDeleted = true;
    body = {};
  }
  else if (path === '/ai/conversations/'+savedChat.id) {
    const older = new URL(req.url()).searchParams.has('before_id');
    body = { ...savedChat, context: { city: 'Hà Nội' }, next_before_id: older ? null : 2, messages: [
      { id: older ? 1 : 2, role: 'assistant', content: older ? 'Tin nhắn đầu tiên.' : 'Tin nhắn đã lưu.', metadata: {} },
    ] };
  }
  else if (path === '/films') body = [{ id: 1, title: 'Phim cũ' }, { id: 2, title: 'Phim mới' }];
  else if (path === '/theaters') body = [{ id: 1, name: 'Rạp cũ' }];
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
  await page.setViewportSize({ width: 1440, height: 900 });
  const launcherButton = page.getByRole('button', { name: 'Hỏi trợ lý', exact: true });
  assert.equal((await launcherButton.boundingBox()).width, 72, 'Launcher starts compact');
  if (process.env.UI_SCREENSHOT_DIR) {
    await mkdir(process.env.UI_SCREENSHOT_DIR, { recursive: true });
    await launcherButton.screenshot({ path: `${process.env.UI_SCREENSHOT_DIR}/ai-launcher-compact.png` });
  }
  await launcherButton.hover();
  await launcherButton.evaluate(el => Promise.all(el.getAnimations().map(animation => animation.finished)));
  assert.equal((await launcherButton.boundingBox()).width, 280, 'Hover expands the launcher');
  await page.mouse.move(0, 0);
  await launcherButton.evaluate(el => Promise.all(el.getAnimations().map(animation => animation.finished)));
  assert.equal((await launcherButton.boundingBox()).width, 72, 'Leaving collapses the launcher');
  await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
  const assistant = page.getByRole('dialog', { name: 'Trợ lý Cinema' });
  await assistant.evaluate(el => Promise.all(el.getAnimations().map(animation => animation.finished)));
  for (const [width, height] of [[320, 568], [390, 844], [768, 1024], [1024, 768], [1440, 900]]) {
    await page.setViewportSize({ width, height });
    await page.keyboard.press('Escape');
    await assistant.waitFor({ state: 'detached' });
    await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
    await assistant.evaluate(el => Promise.all(el.getAnimations().map(animation => animation.finished)));
    assert.equal(await page.getByRole('log').evaluate(el => el.scrollTop), 0, 'An empty conversation opens at the welcome, including short mobile screens');
    const frame = await assistant.boundingBox();
    assert.ok(frame.x >= 0 && frame.y >= 0 && frame.x + frame.width <= width + 1 && frame.y + frame.height <= height + 1, `Chat fits ${width}x${height}: ${JSON.stringify(frame)}`);
    if (width >= 1024) assert.ok(frame.width >= 840, 'Wide assistant leaves room for booking and sources');
    const input = await page.getByLabel('Câu hỏi cho trợ lý').boundingBox();
    assert.equal(await page.getByLabel('Câu hỏi cho trợ lý').evaluate(el => el.labels[0].textContent), 'Câu hỏi cho trợ lý', 'Visible composer label matches its accessible name');
    assert.ok(input.height >= 44 && input.y + input.height <= height, 'Composer remains reachable on short screens');
    assert.equal(await assistant.evaluate(el => el.scrollWidth > el.clientWidth), false, 'Chat does not scroll sideways');
    if (process.env.UI_SCREENSHOT_DIR) {
      await mkdir(process.env.UI_SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({ path: `${process.env.UI_SCREENSHOT_DIR}/ai-welcome-${width}.png` });
    }
  }
  await page.setViewportSize({ width: 375, height: 812 });
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
    await page.screenshot({ path: process.env.UI_SCREENSHOT_DIR+'/ai-cards-375.png' });
  }
  await page.keyboard.press('Escape');
  await assistant.waitFor({ state: 'detached' });
  assert.equal(await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).evaluate(el => el === document.activeElement), true);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).hover();
  assert.equal(await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).evaluate(el => getComputedStyle(el).transform), 'none', 'Reduced motion keeps the launcher still on hover');
  if (process.env.UI_SCREENSHOT_DIR) await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).screenshot({ path: `${process.env.UI_SCREENSHOT_DIR}/ai-launcher.png` });
  await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
  assert.equal(await assistant.evaluate(el => getComputedStyle(el).animationName), 'none', 'Reduced motion skips dialog entrance');
  const composer = page.getByLabel('Câu hỏi cho trợ lý');
  const send = page.getByRole('button', { name: 'Gửi', exact: true });
  const log = page.getByRole('log');
  const filters = page.getByRole('button', { name: /^Bộ lọc/ });
  const filmFilter = page.getByLabel('Phim cho trợ lý');
  await filters.click();
  await filmFilter.locator('option[value="1"]').waitFor({ state: 'attached' });
  assert.equal(await filmFilter.inputValue(), '1');
  await page.getByRole('button', { name: 'Xóa bộ lọc', exact: true }).click();
  await filmFilter.selectOption('2');
  await composer.fill(resetQuestion);
  for (const [failure, notice] of [
    [422, /nêu rõ phim/],
    [429, /sau khoảng một phút/],
    [503, /Mình chưa tra được lúc này/],
    ['network', /Mình chưa tra được lúc này/],
    [409, /Tải lại hội thoại rồi gửi lại/],
  ]) {
    chatFailure = failure;
    const attemptCount = resetRequests.length;
    await send.click();
    await log.getByText(notice).waitFor({ timeout: 5000 });
    assert.equal(resetRequests.length, attemptCount + 1);
    assert.equal(await assistant.getByText(rawChatError, { exact: true }).count(), 0);
    assert.equal(await assistant.locator('.assistant-error').count(), 0);
    assert.equal(await composer.inputValue(), resetQuestion);
    assert.equal(await send.isEnabled(), true);
    assert.deepEqual(resetRequests.at(-1), {
      message: resetQuestion, conversation_id: chatId, context: { film_id: 2, showtime_id: null }, reset_filters: true,
    });
  }
  await page.getByRole('button', { name: 'Lịch sử', exact: true }).click();
  await page.getByRole('button', { name: 'Tải lại hội thoại', exact: true }).click();
  await log.getByText('Lịch chiếu đã lưu.').waitFor();
  assert.equal(await composer.inputValue(), resetQuestion);
  assert.equal(await log.getByText(/Tải lại hội thoại rồi gửi lại/).count(), 0);
  chatFailure = null;
  await send.click();
  await log.getByText('Đã tra lịch với bộ lọc hiện tại.').waitFor();
  assert.equal(resetRequests.at(-1).reset_filters, true);
  assert.equal(resetRequests.at(-1).conversation_id, chatId);
  await filters.click();
  await filmFilter.locator('option[value="2"]').waitFor({ state: 'attached' });
  assert.equal(await filmFilter.inputValue(), '2');
  assert.equal(await page.getByLabel('Rạp cho trợ lý').inputValue(), '');
  assert.equal(await page.getByLabel('Ngày xem cho trợ lý').inputValue(), '');
  await composer.fill(resetQuestion);
  await send.click();
  await log.getByText('Đã tra lịch với bộ lọc hiện tại.').nth(1).waitFor();
  assert.equal(resetRequests.at(-1).reset_filters, undefined);
  await page.getByRole('button', { name: 'Lịch sử', exact: true }).click();
  const savedButton = page.getByRole('button', { name: /^Hội thoại đã lưu/ });
  await savedButton.click();
  await page.getByText('Tin nhắn đã lưu.', { exact: true }).waitFor();
  await filters.click();
  await page.getByRole('button', { name: 'Xóa bộ lọc', exact: true }).waitFor({ timeout: 5000 });
  await page.getByRole('button', { name: 'Tải tin nhắn cũ hơn', exact: true }).click();
  await page.getByText('Tin nhắn đầu tiên.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Lịch sử', exact: true }).click();
  await page.getByRole('button', { name: 'Xóa hội thoại', exact: true }).click();
  await page.getByText('Tin nhắn đã lưu.', { exact: true }).waitFor({ state: 'detached' });
  assert.equal(await savedButton.count(), 0);
  assert.equal(await page.locator(':focus').getAttribute('id'), 'ai-conversation-history');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base+'/admin/documents');
  await page.getByText('Công cụ nâng cao · Kiểm tra truy xuất Knowledge Base', { exact: true }).click();
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
  console.log(JSON.stringify({ passed: ['showtime cards on mobile', 'grouped PDF citation', 'chat error notices and filter reset retry', 'saved chat pagination and deletion',
    'KB retrieval trace', 'KB revision publication'], browserErrors: errors, data: 'isolated fixtures only' }));
} catch (error) {
  if (process.env.UI_SCREENSHOT_DIR) await page.screenshot({ path: process.env.UI_SCREENSHOT_DIR+'/ai-flow-failure.png', fullPage: true });
  console.error((await page.locator('body').innerText()).slice(-4000));
  throw error;
} finally { await browser.close(); }
