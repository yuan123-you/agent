# Agent Cancel and After-Sale Actions Design

**Date:** 2026-08-24

## Goal

Add two buyer-approved Agent actions without allowing the model to mutate orders directly: prepare cancellation of an unpaid order, and prepare creation of an after-sale request for a specific order item.

## Safety model

Both tools only write a ten-minute `agent_action` snapshot. The authenticated buyer confirms or rejects it through the existing action endpoint. Confirmation locks the action row, revalidates ownership and current order/item state, performs the business operation once, and marks the action confirmed in the same transaction.

## Persistence

`agent_action` gains `target_order_id`. A minimal `after_sale` table stores an extensible request compatible with the existing after-sales design: order/item, buyer/merchant, service type, issue category, reason, quantity, requested amount, handler, status, and originating action/conversation. Attachments and merchant workflow are deferred to the already-written full after-sales plan.

## Interfaces

- `order_cancel_prepare(order_id, reason)` supports only buyer-owned `PENDING_PAYMENT` orders.
- `after_sale_prepare(order_id, order_item_id, service_type, issue_category, reason, quantity)` supports buyer-owned `PAID`, `SHIPPED`, or `DELIVERED` orders.
- Existing `/api/v1/order-actions/{actionId}/confirm` becomes type-aware while preserving the order-create response fields.
- Frontend renders a type-specific confirmation card; address editing remains exclusive to `ORDER_CREATE`.

## Out of scope

Merchant approval, evidence upload, return logistics, platform intervention, and simulated refund remain in `2026-08-24-after-sales-service.md`.
