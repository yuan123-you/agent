package com.aimall.backend.order;

/** Existing order commands; the same source state must guard the database write. */
enum OrderTransition {
    PAY("PENDING_PAYMENT", "PAID", "当前订单状态不可支付"),
    CANCEL("PENDING_PAYMENT", "CANCELLED", "仅待支付订单可取消"),
    SHIP("PAID", "SHIPPED", "仅已支付订单可发货"),
    DELIVER("SHIPPED", "DELIVERED", "仅已发货订单可标记送达");

    private final String from;
    private final String to;
    private final String errorMessage;

    OrderTransition(String from, String to, String errorMessage) {
        this.from = from;
        this.to = to;
        this.errorMessage = errorMessage;
    }

    String from() { return from; }
    String to() { return to; }
    String errorMessage() { return errorMessage; }
}
