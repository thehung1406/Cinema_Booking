export function paymentStage(payment) {
  const stage = payment?.fulfillment_status;
  return ["ISSUED", "PROCESSING", "REQUIRES_REVIEW", "FAILED", "AWAITING_PAYMENT"].includes(stage)
    ? stage : "UNKNOWN";
}
export function mayPay(payment, booking) {
  return payment?.can_retry === true && payment.provider_status !== "PAID"
    && ["AWAITING_PAYMENT", "FAILED"].includes(paymentStage(payment))
    && booking?.bookingStatus === "PENDING";
}
