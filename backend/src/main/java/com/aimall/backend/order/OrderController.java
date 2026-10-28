package com.aimall.backend.order;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.OrderItem;
import com.aimall.backend.entity.ProductReview;
import com.aimall.backend.mapper.ProductReviewMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Set;
import java.util.List;
import java.util.Map;

/**
 * 买家端订单接口：/api/v1/orders
 */
@RestController
@RequestMapping("/api/v1/orders")
@RequiredArgsConstructor
public class OrderController {

    private final OrderService orderService;
    private final OrderSseNotifier orderSseNotifier;

    @Autowired
    private ProductReviewMapper reviewMapper;

    @Autowired
    private com.aimall.backend.aftersale.AfterSaleService afterSaleService;

    /** 订单状态订阅（SSE）：状态变更时接收 order_status 事件 */
    @GetMapping(value = "/subscribe", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter subscribe(@AuthenticationPrincipal Long userId) {
        SseEmitter emitter = new SseEmitter(0L);
        orderSseNotifier.register(userId, emitter);
        return emitter;
    }

    @PostMapping
    public ApiResponse<Map<String, Object>> create(@AuthenticationPrincipal Long userId,
                                                   @Valid @RequestBody OrderDtos.CreateOrderRequest req) {
        OrderInfo order = orderService.create(userId, req, "USER", null);
        Map<String, Object> data = new HashMap<>();
        data.put("orderId", order.getId());
        data.put("orderNo", order.getOrderNo());
        data.put("totalAmount", order.getTotalAmount());
        data.put("status", order.getStatus());
        return ApiResponse.ok(data);
    }

    @PostMapping("/{id}/pay")
    public ApiResponse<Map<String, Object>> pay(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        orderService.pay(userId, id);
        return ApiResponse.ok(Map.of("status", "PAID"));
    }

    @PostMapping("/{id}/cancel")
    public ApiResponse<Void> cancel(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        orderService.cancel(userId, id);
        return ApiResponse.ok();
    }

    /** Legacy demo endpoint retained only to fail closed; buyers cannot dispatch business orders. */
    @Deprecated
    @PostMapping("/{id}/simulate-ship")
    public ApiResponse<Void> simulateShip(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        throw new com.aimall.backend.common.BizException(2003, "买家不能执行发货，请由授权的订单管理端登记真实物流");
    }

    /** 买家确认收货（仅本人已发货订单：SHIPPED -> DELIVERED） */
    @PostMapping("/{id}/confirm")
    public ApiResponse<Void> confirmReceipt(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        orderService.confirmReceipt(userId, id);
        return ApiResponse.ok();
    }

    @GetMapping("/my")
    public ApiResponse<PageResult<Map<String, Object>>> my(
            @AuthenticationPrincipal Long userId,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        Page<OrderInfo> result = orderService.myOrders(userId, status, page, size);
        return ApiResponse.ok(PageResult.of(result, order -> toVo(order, userId)));
    }

    @GetMapping("/{id}")
    public ApiResponse<Map<String, Object>> detail(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        OrderInfo order = orderService.requireOwned(userId, id);
        return ApiResponse.ok(toVo(order, userId));
    }

    private Map<String, Object> toVo(OrderInfo order, Long userId) {
        Map<String, Object> vo = new HashMap<>();
        vo.put("orderId", order.getId());
        vo.put("orderNo", order.getOrderNo());
        vo.put("status", order.getStatus());
        vo.put("statusText", statusText(order.getStatus()));
        vo.put("totalAmount", order.getTotalAmount());
        vo.put("source", order.getSource());
        vo.put("logisticsNo", order.getLogisticsNo());
        vo.put("deliveryCompany", order.getDeliveryCompany());
        vo.put("receiverName", order.getReceiverName());
        vo.put("receiverPhone", order.getReceiverPhone());
        vo.put("receiverAddress", order.getReceiverAddress());
        vo.put("createdAt", order.getCreatedAt());
        vo.put("paidAt", order.getPaidAt());
        vo.put("shippedAt", order.getShippedAt());
        vo.put("deliveredAt", order.getDeliveredAt());
        List<OrderItem> items = orderService.itemsOf(order.getId());
        List<Long> productIds = items.stream().map(OrderItem::getProductId).distinct().toList();
        Set<Long> reviewedProducts = productIds.isEmpty() ? Set.of() : new HashSet<>(
                reviewMapper.<Long>selectObjs(new LambdaQueryWrapper<ProductReview>()
                        .select(ProductReview::getProductId)
                        .eq(ProductReview::getUserId, userId)
                        .in(ProductReview::getProductId, productIds)));
        vo.put("discountAmount", order.getDiscountAmount());
        if (afterSaleService != null) {
            vo.put("afterSaleItems", afterSaleService.eligibility(userId, order.getId()));
            vo.put("afterSales", afterSaleService.forOrder(userId, order.getId()));
            vo.put("refundedAmount", afterSaleService.refundedAmount(order.getId()));
        }
        vo.put("items", items.stream().map(i -> {
            Map<String, Object> itemVo = new HashMap<>();
            boolean reviewed = reviewedProducts.contains(i.getProductId());
            itemVo.put("orderItemId", i.getId());
            itemVo.put("reviewed", reviewed);
            itemVo.put("canReview", "DELIVERED".equals(order.getStatus()) && !reviewed);
            itemVo.put("productId", i.getProductId());
            itemVo.put("productName", i.getProductName());
            itemVo.put("productImage", i.getProductImage());
            itemVo.put("price", i.getPrice());
            itemVo.put("quantity", i.getQuantity());
            itemVo.put("subtotal", i.getSubtotal());
            itemVo.put("skuSp", i.getSkuSp());
            return itemVo;
        }).toList());
        return vo;
    }

    private String statusText(String status) {
        return switch (status) {
            case "PENDING_PAYMENT" -> "待支付";
            case "PAID" -> "已支付";
            case "SHIPPED" -> "已发货";
            case "DELIVERED" -> "已送达";
            case "CANCELLED" -> "已取消";
            case "REFUNDED" -> "已退款";
            default -> status;
        };
    }
}
