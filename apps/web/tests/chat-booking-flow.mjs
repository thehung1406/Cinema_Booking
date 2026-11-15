import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const browser = await chromium.launch(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {});
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:5174';

async function run({ typed, lookupTool, food, retry, conflict }) {
  const page = await browser.newPage({ viewport: { width: 375, height: 760 } });
  await page.addInitScript(() => localStorage.setItem('userInfo', JSON.stringify({ id: 7, access_token: 'mock-token', role: 'USER' })));
  const reservation = '915167e4-6130-4ad0-826c-7922986d41da';
  const expiry = new Date(Date.now() + 600000).toISOString();
  const conversation = '11111111-1111-4111-8111-111111111111';
  const show = { film_title: 'Phim test', theater_name: 'Rạp test', room_name: 'Phòng 1', show_date: '2030-12-01', start_time: '19:30:00' };
  const cards = [10, 11].map(id => ({ ...show, showtime_id: id, party_size: 2, available_seats: 10, min_ticket_price: '90000', minimum_total: '180000', url: `/seat-selection/${id}` }));
  const recommendations = lookupTool ? [20, 21, 22].map(id => ({
    ...cards[0], showtime_id: id, film_title: 'Phim cũ', url: `/seat-selection/${id}`,
  })) : cards;
  const sources = cards.map(card => ({ id: `showtime:${card.showtime_id}`, kind: 'live', title: `Suất ${card.showtime_id}`, url: card.url }));
  let held = [];
  const openedShowtimes = [];
  const checkouts = [];
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.slice(4);
    let body = [];
    let status = 200;
    if (path === '/ai/chat') {
      const message = request.postDataJSON().message;
      const response = { conversation_id: conversation, answer: 'Có suất phù hợp.', context: {}, cards: recommendations, showtime_options: true, as_of: new Date().toISOString() };
      if (message === 'Cho tôi xem vé vừa mua') {
        body = { ...response, answer: 'Vé đã được phát hành.', cards: [], booking: { booking_id: 77, film_title: 'Phim test', seat_count: 2, total_amount: '240000', ticket_url: '/payment-result?bookingId=77' } };
      } else if (message === 'Tìm suất không có kết quả') {
        body = { ...response, answer: 'Chưa có suất phù hợp.', cards: [], tool: lookupTool, showtime_options: !lookupTool };
      } else if (message === 'Tìm suất của Phim test') {
        body = { ...response, answer: 'Đã tìm được lịch chiếu của Phim test.', cards: [], tool: lookupTool, showtime_options: true, sources };
        if (lookupTool === 'react_lookup') {
          body.sources = [...sources, { id: 'price:1', kind: 'live', title: 'Ghế thường', url: '/seat-selection/10' }];
        }
        body.links = body.sources.map(({ title, url }) => ({ title, url }));
      } else body = response;
    }
    if (path.startsWith('/showtimes/')) openedShowtimes.push(path);
    if (path === '/showtimes/11') body = show;
    if (path === '/seats/showtime/11') body = [4, 5].map(id => ({ seat_id: id, seat_name: `A${id + 1}`, price: 90000, status: held.includes(id) ? 'HOLD' : 'AVAILABLE', is_held_by_me: held.includes(id), hold_expired_at: held.includes(id) ? expiry : null, reservation_id: held.includes(id) ? reservation : null }));
    if (path === '/food-items') body = [{ id: 3, name: 'Combo test', category: 'COMBO', price: '60000.00' }];
    if (path === '/ai/booking/hold') {
      const payload = request.postDataJSON();
      assert.deepEqual(payload, { showtime_id: 11, seat_ids: [4, 5] });
      held = payload.seat_ids;
      body = held.map(id => ({ seat_id: id, seat_name: `A${id + 1}`, status: 'HOLD', reservation_id: reservation, hold_expired_at: expiry }));
    }
    if (path === '/ai/booking/checkout') {
      checkouts.push({ key: request.headers()['idempotency-key'], body: request.postDataJSON() });
      if (conflict) { status = 409; body = { detail: 'Reservation đã có đơn' }; }
      else if (retry && checkouts.length === 1) { status = 503; body = { detail: 'Chưa nhận được phản hồi.' }; }
      else { status = 201; body = { bookingId: 77, expiresAt: expiry }; }
    }
    if (path === '/bookings/77') body = { bookingId: 77, bookingStatus: 'PENDING', totalAmount: 240000, seats: [] };
    if (path === '/payment/status/77') body = { booking_id: 77, provider_status: 'PENDING', fulfillment_status: 'AWAITING_PAYMENT', can_retry: true };
    await route.fulfill({ status, json: body });
  });

  async function openChat() {
    await page.getByRole('button', { name: 'Hỏi trợ lý', exact: true }).click();
    return page.getByRole('dialog', { name: 'Trợ lý Cinema' });
  }
  async function ask(chat, message) {
    await chat.getByLabel('Câu hỏi cho trợ lý').fill(message);
    await chat.getByRole('button', { name: 'Gửi', exact: true }).click();
  }

  try {
    await page.goto(`${base}/about`);
    let chat = await openChat();
    await ask(chat, 'Đặt hai vé phim test tối nay');
    await chat.getByText('Có suất phù hợp.', { exact: true }).waitFor();
    if (typed) {
      await ask(chat, 'Tìm suất không có kết quả');
      await chat.getByText('Chưa có suất phù hợp.').waitFor();
      await ask(chat, 'Suất thứ hai');
      await chat.getByText('Không có suất tương ứng trong danh sách gần nhất.').waitFor();
      if (lookupTool) {
        await ask(chat, 'Tìm suất của Phim test');
        await chat.getByText('Đã tìm được lịch chiếu của Phim test.').waitFor();
        await ask(chat, 'Suất thứ ba');
        await chat.getByText('Không có suất tương ứng trong danh sách gần nhất.').waitFor();
        assert.deepEqual(openedShowtimes, []);
      } else {
        await ask(chat, 'Đặt hai vé phim test tối nay');
        await chat.getByText('Có suất phù hợp.', { exact: true }).nth(1).waitFor();
      }
      await ask(chat, lookupTool ? 'Suất thứ hai' : 'Suất thứ hai, ghế A5 A6');
      await chat.getByRole('region', { name: 'Đặt vé trong chat' }).getByRole('heading', { name: 'Phim test' }).waitFor();
      assert.deepEqual(openedShowtimes, ['/showtimes/11']);
      if (lookupTool) await ask(chat, 'Ghế A5 A6');
    }
    else {
      await chat.getByRole('button', { name: 'Đặt trong chat', exact: true }).nth(1).click();
      await chat.getByRole('button', { name: /^Ghế A5,/ }).click();
      await chat.getByRole('button', { name: /^Ghế A6,/ }).click();
    }
    assert.equal(checkouts.length, 0);
    await chat.getByRole('button', { name: 'Giữ ghế', exact: true }).click();
    if (food) await chat.getByRole('button', { name: 'Thêm Combo test' }).click();
    else await chat.getByRole('button', { name: 'Bỏ qua đồ ăn' }).click();
    assert.equal(checkouts.length, 0);
    await chat.getByRole('button', { name: 'Xác nhận đặt vé' }).click();
    if (conflict) {
      await chat.getByText('Reservation đã có đơn', { exact: true }).waitFor();
      await chat.getByRole('link', { name: 'Xem đơn của tôi' }).waitFor();
      await chat.getByRole('button', { name: 'Đóng bước đặt vé' }).click();
      assert.equal(await chat.getByRole('region', { name: 'Đặt vé trong chat' }).count(), 0);
      return;
    }
    if (retry) {
      await chat.getByRole('button', { name: 'Thử lại tạo đơn' }).waitFor();
      await page.reload();
      chat = await openChat();
      await chat.getByRole('button', { name: 'Thử lại tạo đơn' }).click();
    }
    await page.waitForURL('**/payment/77');
    assert.ok(checkouts[0].key);
    assert.equal(checkouts[0].body.total_amount, food ? '240000.00' : '180000.00');
    assert.deepEqual(checkouts[0].body.food_items, food ? [{ food_item_id: 3, quantity: 1 }] : []);
    if (retry) assert.deepEqual(checkouts[0], checkouts[1]);
    await page.goto(`${base}/about`);
    chat = await openChat();
    await ask(chat, 'Cho tôi xem vé vừa mua');
    assert.equal(await chat.getByRole('link', { name: 'Xem vé' }).getAttribute('href'), '/payment-result?bookingId=77');
    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
}

try {
  await run({ typed: true, food: true, retry: true });
  await run({ typed: true, lookupTool: 'get_showtimes', food: false });
  await run({ typed: true, lookupTool: 'react_lookup', food: false });
  await run({ typed: false, food: false, retry: false });
  await run({ typed: false, food: false, conflict: true });
  console.log('Chat booking passed: typed selection from recommendations and lookups, button selection, combo and skip, idempotent retry after reload, existing order recovery, issued ticket link.');
} finally {
  await browser.close();
}
