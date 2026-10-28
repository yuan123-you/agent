package com.aimall.backend.aftersale;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.OrderItem;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

public final class AfterSalePolicy {
    private AfterSalePolicy() {}
    public static final Set<String> RELEASED = Set.of("CANCELLED", "REJECTED", "RESOLVED");
    public static final Set<String> TERMINAL = Set.of("CANCELLED", "REJECTED", "REFUNDED", "EXCHANGED", "RESOLVED");
    public static List<String> services(String status) {
        return switch (status) {
            case "PAID" -> List.of("REFUND_ONLY");
            case "SHIPPED", "DELIVERED" -> List.of("REFUND_ONLY", "RETURN_REFUND", "EXCHANGE");
            default -> List.of();
        };
    }
    public static BigDecimal allocation(BigDecimal paid, List<OrderItem> source, Long itemId) {
        var items = source.stream().sorted(Comparator.comparing(OrderItem::getId)).toList();
        BigDecimal gross = items.stream().map(OrderItem::getSubtotal).reduce(BigDecimal.ZERO, BigDecimal::add);
        if (paid == null || paid.signum() < 0 || gross.signum() <= 0 || paid.compareTo(gross) > 0) throw invalid("订单实付金额无效");
        BigDecimal cumulative = BigDecimal.ZERO, previous = BigDecimal.ZERO;
        for (var item : items) {
            cumulative = cumulative.add(item.getSubtotal());
            BigDecimal allocated = paid.multiply(cumulative).divide(gross, 2, RoundingMode.HALF_UP);
            if (Objects.equals(item.getId(), itemId)) return allocated.subtract(previous);
            previous = allocated;
        }
        throw invalid("订单商品不存在");
    }
    public static BigDecimal refundCap(BigDecimal allocated, int purchased, int consumed, int quantity, BigDecimal reserved) {
        if (purchased <= 0 || consumed < 0 || quantity <= 0 || quantity > purchased - consumed) throw invalid("申请数量超过可售后数量");
        BigDecimal before = allocated.multiply(BigDecimal.valueOf(consumed)).divide(BigDecimal.valueOf(purchased), 2, RoundingMode.HALF_UP);
        BigDecimal after = allocated.multiply(BigDecimal.valueOf((long) consumed + quantity)).divide(BigDecimal.valueOf(purchased), 2, RoundingMode.HALF_UP);
        return after.subtract(before).min(allocated.subtract(reserved)).max(BigDecimal.ZERO).setScale(2, RoundingMode.HALF_UP);
    }
    public static String next(String type, String status, String action) {
        if ("CANCEL".equals(action) && Set.of("PENDING_MERCHANT","PENDING_PLATFORM","WAITING_RETURN").contains(status)) return "CANCELLED";
        if ("APPEAL".equals(action) && "REJECTED".equals(status)) return "PENDING_PLATFORM";
        if (Set.of("PENDING_MERCHANT","PENDING_PLATFORM").contains(status)) {
            if ("REJECT".equals(action)) return "REJECTED";
            if ("APPROVE".equals(action)) return switch (type) {
                case "REFUND_ONLY" -> "WAITING_REFUND";
                case "RETURN_REFUND", "EXCHANGE" -> "WAITING_RETURN";
                case "ISSUE_REPORT" -> "RESOLVED";
                default -> throw invalid("售后类型无效");
            };
        }
        if ("CONVERT_REFUND".equals(action) && "EXCHANGE".equals(type) && "WAITING_EXCHANGE".equals(status)) return "WAITING_REFUND";
        if ("RETURN".equals(action) && "WAITING_RETURN".equals(status)) return "RETURN_SHIPPED";
        if ("RECEIVE".equals(action) && "RETURN_SHIPPED".equals(status)) return "EXCHANGE".equals(type) ? "WAITING_EXCHANGE" : "WAITING_REFUND";
        if ("REFUND".equals(action) && "WAITING_REFUND".equals(status) && Set.of("REFUND_ONLY","RETURN_REFUND").contains(type)) return "REFUNDED";
        if ("SHIP_EXCHANGE".equals(action) && "WAITING_EXCHANGE".equals(status) && "EXCHANGE".equals(type)) return "EXCHANGE_SHIPPED";
        if ("CONFIRM_EXCHANGE".equals(action) && "EXCHANGE_SHIPPED".equals(status)) return "EXCHANGED";
        throw invalid("当前售后状态不支持该操作，请刷新后重试");
    }
    public static BizException invalid(String message) { return new BizException(2004, message); }
}
