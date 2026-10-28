-- Immutable purchased quantities remain in order_item; this marker records only released fulfillment units.
ALTER TABLE after_sale ADD COLUMN cancelled_fulfillment_quantity INT NOT NULL DEFAULT 0;

-- Conservative backfill: only a completed refund-only case on an order still PAID and never shipped
-- proves a pre-shipment release. Ambiguous terminal historical orders retain zero; do not infer from money.
UPDATE after_sale SET cancelled_fulfillment_quantity = quantity
WHERE service_type = 'REFUND_ONLY' AND status = 'REFUNDED' AND quantity > 0
  AND EXISTS (SELECT 1 FROM order_info o WHERE o.id = after_sale.order_id
              AND o.status = 'PAID' AND o.shipped_at IS NULL);
