package com.aimall.backend.order;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.internal.AgentOrderActionService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/** Buyer-owned explicit confirmation endpoint for prepared AI order actions. */
@RestController
@RequestMapping("/api/v1/order-actions")
@RequiredArgsConstructor
public class OrderActionController {
    private final AgentOrderActionService actionService;

    @PostMapping("/{actionId}/confirm")
    public ApiResponse<Map<String, Object>> confirm(@AuthenticationPrincipal Long userId,
                                                    @PathVariable String actionId) {
        OrderInfo order = actionService.confirm(userId, actionId);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("orderId", order.getId());
        result.put("orderNo", order.getOrderNo());
        result.put("status", order.getStatus());
        result.put("totalAmount", order.getTotalAmount());
        return ApiResponse.ok(result);
    }
}
