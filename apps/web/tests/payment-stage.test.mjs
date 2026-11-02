import test from "node:test";
import assert from "node:assert/strict";
import { paymentStage, mayPay } from "../src/services/paymentStage.js";
import { paymentState } from "../src/utils/formatters.js";
test("Provider success alone never implies a ticket or another charge", () => {
  assert.equal(paymentStage({ status: "success", provider_status: "PAID" }), "UNKNOWN");
  assert.equal(paymentStage({ fulfillment_status: "PROCESSING" }), "PROCESSING");
  assert.equal(mayPay({ provider_status: "PAID", fulfillment_status: "PROCESSING", can_retry: true }, { bookingStatus: "PENDING" }), false);
  assert.equal(paymentState({ paymentStatus: "PAID", bookingStatus: "EXPIRED" }), "review");
});
test("Retry requires a fresh payable state and a pending Booking", () => {
  const status = { provider_status: "FAILED", fulfillment_status: "FAILED", can_retry: true };
  assert.equal(mayPay(status, { bookingStatus: "PENDING" }), true);
  assert.equal(mayPay(status, { bookingStatus: "EXPIRED" }), false);
  assert.equal(mayPay({ ...status, can_retry: false }, { bookingStatus: "PENDING" }), false);
});
