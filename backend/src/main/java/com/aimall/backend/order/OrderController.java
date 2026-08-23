package com.aimall.backend.order;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.OrderItem;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.HashMap;
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

    @GetMapping("/my")
    public ApiResponse<PageResult<Map<String, Object>>> my(
            @AuthenticationPrincipal Long userId,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        Page<OrderInfo> result = orderService.myOrders(userId, status, page, size);
        return ApiResponse.ok(PageResult.of(result, this::toVo));
    }

    @GetMapping("/{id}")
    public ApiResponse<Map<String, Object>> detail(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        OrderInfo order = orderService.requireOwned(userId, id);
        return ApiResponse.ok(toVo(order));
    }

    private Map<String, Object> toVo(OrderInfo order) {
        Map<String, Object> vo = new HashMap<>();
        vo.put("orderId", order.getId());
        vo.put("orderNo", order.getOrderNo());
        vo.put("status", order.getStatus());
        vo.put("statusText", statusText(order.getStatus()));
        vo.put("totalAmount", order.getTotalAmount());
        vo.put("source", order.getSource());
        vo.put("logisticsNo", order.getLogisticsNo());
        vo.put("receiverName", order.getReceiverName());
        vo.put("receiverPhone", order.getReceiverPhone());
        vo.put("receiverAddress", order.getReceiverAddress());
        vo.put("createdAt", order.getCreatedAt());
        vo.put("paidAt", order.getPaidAt());
        vo.put("shippedAt", order.getShippedAt());
        vo.put("deliveredAt", order.getDeliveredAt());
        List<OrderItem> items = orderService.itemsOf(order.getId());
        vo.put("items", items.stream().map(i -> {
            Map<String, Object> itemVo = new HashMap<>();
            itemVo.put("productId", i.getProductId());
            itemVo.put("productName", i.getProductName());
            itemVo.put("productImage", i.getProductImage());
            itemVo.put("price", i.getPrice());
            itemVo.put("quantity", i.getQuantity());
            itemVo.put("subtotal", i.getSubtotal());
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
            default -> status;
        };
    }
}
