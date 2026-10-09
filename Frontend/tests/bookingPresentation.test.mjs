import assert from "node:assert/strict";
import test from "node:test";
import {
  formatCurrency,
  formatDate,
  formatTime,
  localDateInput,
  paymentState,
} from "../src/utils/formatters.js";
import {
  classifyMovies,
  isNowShowing,
  isUpcoming,
} from "../src/utils/filmUtils.js";

test("payment presentation distinguishes confirmed failure from pending or unknown", () => {
  assert.equal(paymentState({ paymentStatus: "PAID" }), "success");
  for (const paymentStatus of ["FAILED", "CANCELLED"])
    assert.equal(paymentState({ paymentStatus }), "failed");
  assert.equal(paymentState({ bookingStatus: "CANCELLED" }), "failed");
  for (const paymentStatus of ["PENDING", undefined, "UNKNOWN"])
    assert.equal(paymentState({ paymentStatus }), "pending");
});

test("Vietnamese currency preserves zero and does not fabricate missing prices", () => {
  assert.match(formatCurrency("125000"), /125\.000/);
  assert.match(formatCurrency(0), /0/);
  for (const value of [null, undefined, "", "invalid"])
    assert.equal(formatCurrency(value), "Chưa có giá");
});

test("dates and times support both API time-only and datetime values in Vietnam", () => {
  assert.equal(formatTime("18:30:00"), "18:30");
  assert.equal(formatTime("2026-10-09T18:30:00Z"), "01:30");
  assert.equal(localDateInput(new Date("2026-10-09T18:30:00Z")), "2026-10-10");
  assert.equal(formatDate("2026-10-09"), "09/10/2026");
  assert.equal(formatDate("invalid"), "Chưa xác định");
  assert.equal(formatTime(null), "Chưa xác định");
});

test("film classification uses release and end dates, never an invented 90 day run", () => {
  const date = new Date("2026-10-09T18:30:00Z");
  assert.equal(
    isNowShowing({ release_date: "2026-10-10", end_date: "2026-10-10" }, date),
    true,
  );
  assert.equal(isNowShowing({ release_date: "2025-01-01" }, date), true);
  assert.equal(
    isNowShowing({ release_date: "2026-01-01", end_date: "2026-10-09" }, date),
    false,
  );
  assert.equal(isUpcoming({ release_date: "2026-10-11" }, date), true);
  assert.equal(
    isUpcoming({ release_date: "2026-10-01", end_date: "2026-10-02" }, date),
    false,
  );
  const ended = { release_date: "2020-01-01", end_date: "2020-02-01" };
  const unknown = { title: "Unknown" };
  assert.deepEqual(classifyMovies([ended, unknown]), {
    nowShowing: [],
    upcoming: [],
  });
});
