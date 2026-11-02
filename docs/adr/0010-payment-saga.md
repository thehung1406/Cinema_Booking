# ADR 0010: Payment collects money; Booking accepts one funding result

Status: accepted for the local M9 cutover, 2026-11-02.

The shared Booking/payment transaction ends at M9. Payment preserves provider
results independently; Booking owns the only transaction that confirms seats and
issues tickets. A callback cannot synchronously promise a ticket. Use an outbox
capture and an inbox-protected Booking transaction, followed by a sealed result
and Payment fulfillment state. HTTP result polling repairs a lost acknowledgement.

Keep one reusable pending attempt. Failed attempts can be replaced until checkout
expires, and old failed attempts can still receive late provider success. Preserve
both collections if two attempts become PAID; the second cannot issue more tickets.
Reject late captures against an expired/replaced hold and open a durable money
case. Never conceal collected money by changing PAID to FAILED.

No automatic refund is implemented without a verified provider refund integration.
Operational retries are audited, reuse event identity, and do not claim to refund
or resolve money. Reconciliation distinguishes transient missing acknowledgements
from permanent amount/duplicate/rejected collection cases.

Historical original payment columns and sequence high-water are transferred under
a frozen writer boundary. Existing valid ticket evidence becomes accepted Booking
receipts and Payment fulfillment without synthesizing captures or sending emails.
Booking retains a fenced archive for migration recovery and old-mode regression;
service-mode reports use local accepted receipts instead of archive payments.
DB ownership plus the route guard prevents reopening callbacks by resetting env.
