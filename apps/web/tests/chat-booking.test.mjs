import assert from 'node:assert/strict';
import { test } from 'node:test';
import { bookingCommand, checkoutPayload, seatIdsForCommand } from '../src/services/chatBooking.js';

test('recognizes ordinal and seat commands without intercepting general questions', () => {
  assert.deepEqual(bookingCommand('Suất thứ hai, ghế a5 A6'), { ordinal: 2, seatNames: ['A5', 'A6'] });
  assert.deepEqual(bookingCommand('suất thứ 2'), { ordinal: 2, seatNames: [] });
  assert.deepEqual(bookingCommand('Ghế A5, A6'), { ordinal: null, seatNames: ['A5', 'A6'] });
  assert.equal(bookingCommand('Ghế A5 có giá bao nhiêu?'), null);
  assert.equal(bookingCommand('Xác nhận đặt vé'), null);
});

test('resolves seat names only to available seats of the selected showtime', () => {
  const seats = [
    { seat_id: 4, seat_name: 'A5', status: 'AVAILABLE' },
    { seat_id: 6, seat_name: 'A6', status: 'BOOKED' },
  ];
  assert.deepEqual(seatIdsForCommand(['A5'], seats), [4]);
  assert.throws(() => seatIdsForCommand(['A5', 'A5'], seats));
  assert.throws(() => seatIdsForCommand(['A6'], seats));
  assert.throws(() => seatIdsForCommand(['A7'], seats));
});

test('checkout uses cents and an empty item list when food is skipped', () => {
  const seats = [{ seat_id: 1, price: '10.20' }, { seat_id: 2, price: 20.35 }];
  const body = checkoutPayload(11, 'reservation-id', seats, [{ id: 3, price: '5.15' }], { 3: 2 });
  assert.deepEqual(body, {
    showtime_id: 11, reservation_id: 'reservation-id', total_amount: '40.85',
    seats: [{ seat_id: 1, price: '10.20' }, { seat_id: 2, price: '20.35' }],
    food_items: [{ food_item_id: 3, quantity: 2 }],
  });
  assert.equal(checkoutPayload(11, 'reservation-id', seats, [], {}).total_amount, '30.55');
});
