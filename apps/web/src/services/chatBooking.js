const ORDINALS = ['nhat', 'hai', 'ba', 'tu', 'nam', 'sau', 'bay', 'tam', 'chin', 'muoi'];

export function bookingCommand(message) {
  const text = message.normalize('NFD').replace(/\p{M}/gu, '').replace(/đ/gi, 'd').trim().toLowerCase();
  const match = /^(?:suat\s+thu\s+(\d{1,2}|nhat|hai|ba|tu|bon|nam|sau|bay|tam|chin|muoi))?(?:\s*[,;]?\s*ghe\s+([a-z]+\d+(?:[\s,]+[a-z]+\d+)*))?[.!]?$/.exec(text);
  if (!match || (!match[1] && !match[2])) return null;
  const ordinal = match[1] ? (/^\d+$/.test(match[1]) ? Number(match[1]) : ORDINALS.indexOf(match[1] === 'bon' ? 'tu' : match[1]) + 1) : null;
  return { ordinal, seatNames: match[2]?.toUpperCase().split(/[\s,]+/) || [] };
}

export function seatIdsForCommand(names, seats) {
  if (names.length > 20 || new Set(names).size !== names.length) throw new Error('Hãy chọn tối đa 20 ghế và chỉ nhập mỗi ghế một lần.');
  return names.map(name => {
    const matches = seats.filter(seat => seat.seat_name.toUpperCase() === name);
    if (matches.length !== 1 || matches[0].status !== 'AVAILABLE') throw new Error(`Ghế ${name} không có hoặc không còn trống. Hãy chọn lại.`);
    return matches[0].seat_id;
  });
}

export function checkoutPayload(showtimeId, reservationId, seats, items, quantities) {
  const cents = price => {
    if (!/^\d{1,10}(?:\.\d{1,2})?$/.test(String(price))) throw new Error('Chưa xác minh được giá. Hãy tải lại dữ liệu.');
    return Math.round(Number(price) * 100);
  };
  let total = 0;
  const seatLines = seats.map(seat => {
    const price = cents(seat.price);
    total += price;
    return { seat_id: seat.seat_id, price: (price / 100).toFixed(2) };
  });
  const food = items.filter(item => quantities[item.id] > 0).map(item => {
    total += cents(item.price) * quantities[item.id];
    return { food_item_id: item.id, quantity: quantities[item.id] };
  });
  return {
    showtime_id: showtimeId, reservation_id: reservationId, seats: seatLines,
    food_items: food, total_amount: (total / 100).toFixed(2),
  };
}
