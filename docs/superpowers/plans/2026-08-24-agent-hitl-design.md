# Agent Human-in-the-loop Design

## Goal

Turn AI-assisted order creation into a durable human approval flow: LangGraph decides when to call the order preparation tool, but no order is created until the authenticated buyer reviews or edits delivery data and explicitly confirms in the frontend. The buyer may also reject the action.

## Architecture

The existing LangGraph ReAct path remains responsible for intent routing and tool selection. `order_create` is a safe prepare-only tool that writes a `PENDING` `agent_action` record and emits a structured SSE action. This database record is the durable interrupt boundary: the graph request can end while the business action remains paused across processes and restarts.

The frontend opens an Element Plus dialog from the action card. Approval sends editable receiver name, phone, and address to the Spring backend. Rejection also calls the backend. The backend authenticates ownership, locks the action row, validates state and expiry, applies only the approved delivery fields, rechecks product availability/current price, and either creates exactly one order or marks the action cancelled.

## Decisions

- Use the existing LangGraph graph and prepare-only tool rather than adding an in-memory LangGraph checkpointer.
- Persist HITL state in MySQL `agent_action`; this is production-safe and survives AI-service restarts.
- Keep identity server-owned; request bodies cannot choose `userId`.
- Make cancel a backend state transition, not a frontend-only visual change.
- Permit edits only to delivery fields. Product, quantity, conversation and owner remain from the server snapshot.
- Revalidate price and inventory at confirmation time.

## User Flow

1. Buyer asks the Agent to purchase a known product.
2. LangGraph routes the request and the Agent calls `order_create`.
3. Backend stores a PENDING action; SSE renders an action card.
4. Buyer selects “核对并确认”, edits the form, then submits; or selects “取消”.
5. Backend receives the decision and performs the guarded state transition.
6. Frontend updates the card to CONFIRMED/CANCELLED/FAILED/EXPIRED.
